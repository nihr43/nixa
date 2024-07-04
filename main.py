import os
import sys
import time
import yaml
import json
import paramiko
import difflib
import uuid
import argparse
import traceback
import logging
import ipaddress
from termcolor import colored
from jinja2 import Environment, FileSystemLoader
from concurrent.futures import ThreadPoolExecutor, as_completed

logging.getLogger("paramiko").setLevel(logging.CRITICAL)


class Cluster:
    def __init__(self, join_address, join_token, nodes, nix_channel):
        self.join_address = join_address
        self.join_token = join_token
        self.nodes = nodes
        self.nix_channel = nix_channel

    @classmethod
    def from_yaml(cls, file_path):
        with open(file_path, "r") as file:
            data = yaml.safe_load(file)
            join_address = data["join_address"]
            join_token = data["join_token"]
            nix_channel = data["nix_channel"]
            nodes = []
            for n, d in data["nodes"].items():
                nodes.append(Node(n, d["initiator"], d["boot_device"]))
            return cls(join_address, join_token, nodes, nix_channel)

    def k8s_ready(self):
        with ThreadPoolExecutor(max_workers=8) as pool:
            futures = {pool.submit(n.k8s_ready): n for n in self.nodes}

        for future in as_completed(futures):
            try:
                result = future.result()
                if result:
                    print(result)
            except Exception:
                traceback.print_exc()
                sys.exit(1)

    def ceph_ready(self):
        self.nodes[0].ceph_ready()

    def daemonsets_ready(self, namespace: str):
        i = 0
        while i < 600:
            i += 1
            try:
                stdin, stdout, stderr = self.nodes[0].ssh.exec_command(
                    f"kubectl get daemonset -o json -n {namespace}"
                )
                js = json.loads(stdout.read().decode())
                desired_healthy = len(js["items"])
                healthy = 0
                for ds in js["items"]:
                    if (
                        ds["status"]["numberAvailable"]
                        == ds["status"]["desiredNumberScheduled"]
                    ):
                        healthy += 1
                if healthy == desired_healthy:
                    print(
                        colored(
                            f"{healthy} daemonsets healthy in namespace {namespace}",
                            "green",
                        )
                    )
                    return
                else:
                    time.sleep(1)
                    continue
            except json.decoder.JSONDecodeError:
                time.sleep(1)
                continue

        raise TimeoutError

    def deployments_ready(self, namespace):
        i = 0
        while i < 600:
            i += 1
            try:
                stdin, stdout, stderr = self.nodes[0].ssh.exec_command(
                    f"kubectl get deployment -o json -n {namespace}"
                )
                js = json.loads(stdout.read().decode())
                desired_healthy = len(js["items"])
                healthy = 0
                for d in js["items"]:
                    for condition in d["status"]["conditions"]:
                        if (
                            condition["reason"] == "MinimumReplicasAvailable"
                            and condition["status"] == "True"
                        ):
                            healthy += 1
                            break
                if healthy == desired_healthy:
                    print(
                        colored(
                            f"{healthy} deployments healthy in namespace {namespace}",
                            "green",
                        )
                    )
                    return
                else:
                    time.sleep(1)
                    continue
            except json.decoder.JSONDecodeError:
                time.sleep(1)
                continue

        raise TimeoutError


class Node:
    def __init__(self, ip, initiator, boot_device):
        self.ip = ip
        self.boot_device = boot_device
        self.initiator = initiator
        self.name = uuid.uuid5(uuid.NAMESPACE_OID, self.ip)
        self.ssh_ready()
        self.interface = self.get_interface()
        self.gateway = self.get_gateway()

    def get_interface(self):
        stdin, stdout, stderr = self.ssh.exec_command(
            "ip r get 1.1.1.1 | awk '/via/{print $5}'"
        )
        interface = stdout.read().decode().strip()
        if interface.startswith(("eth", "eno", "enp")):
            return interface
        else:
            raise NotImplementedError(interface)

    def get_gateway(self):
        stdin, stdout, stderr = self.ssh.exec_command(
            "ip r get 1.1.1.1 | awk '/via/{print $3}'"
        )
        gw = stdout.read().decode().strip()
        try:
            ipaddress.IPv4Address(gw)
            return gw
        except ipaddress.AddressValueError as e:
            raise e

    def ssh_ready(self):
        i = 0
        while i < 300:
            i += 1
            if i % 10 == 0:
                print("Waiting for {} become reachable".format(self.name))
            try:
                self.ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
                self.ssh.connect(self.ip, 22, "root")
                self.sftp = self.ssh.open_sftp()
                self.ssh.exec_command("hostname")
                print("{} is reachable".format(self.name))
                return
            except AttributeError:
                self.ssh = paramiko.SSHClient()
                continue
            except (
                paramiko.ssh_exception.SSHException,
                paramiko.ssh_exception.NoValidConnectionsError,
                TimeoutError,
                EOFError,
            ):
                time.sleep(1)
                continue

        raise TimeoutError

    def k8s_ready(self):
        i = 0
        while i < 300:
            i += 1
            try:
                stdin, stdout, stderr = self.ssh.exec_command(
                    "kubectl get node {} -o json".format(self.name)
                )
                node_json = json.loads(stdout.read().decode())
                for condition in node_json["status"]["conditions"]:
                    if (
                        condition["reason"] == "KubeletReady"
                        and condition["status"] == "True"
                    ):
                        print(colored("k8s is ready on {}".format(self.name), "green"))
                        return
                    elif (
                        condition["reason"] == "KubeletReady"
                        and condition["status"] == "False"
                    ):
                        print("k8s is not ready on {}".format(self.name))
                        time.sleep(1)
                        continue
            except json.decoder.JSONDecodeError:
                time.sleep(1)
                continue

        raise TimeoutError

    def ceph_ready(self):
        i = 0
        while i < 600:
            i += 1
            stdin, stdout, stderr = self.ssh.exec_command(
                "kubectl -n rook-ceph exec deployment/rook-ceph-tools --pod-running-timeout=5m -- ceph status -f json"
            )
            try:
                js = json.loads(stdout.read().decode())
            except json.decoder.JSONDecodeError:
                time.sleep(1)
                continue
            health = js["health"]["status"]
            if i % 10 == 0 and health != "HEALTH_OK":
                print(f"ceph state is {health}")
            if health == "HEALTH_OK":
                print(colored(f"ceph state is {health}", "green"))
                return
            else:
                time.sleep(1)

        raise TimeoutError


def reconcile(node, cluster, args):
    file_loader = FileSystemLoader("templates/")
    env = Environment(loader=file_loader)
    template = env.get_template("configuration.nix")
    output = template.render(node=node, cluster=cluster)

    output_file_path = "artifacts/{}".format(node.name)
    with open(output_file_path, "w") as f:
        f.write(output)

    with open(output_file_path, "r") as local_file:
        local_config = local_file.readlines()

    with node.sftp.file("/etc/nixos/configuration.nix", "r") as remote_file:
        remote_config = remote_file.readlines()
        remote_file.seek(0)
        remote_config_str = remote_file.read()

    diff = list(difflib.unified_diff(remote_config, local_config))
    diff_formatted = colored("".join(diff).strip(), "yellow")

    if diff:
        print("{} modified:".format(node.name))
        print(diff_formatted)
        node.sftp.put(output_file_path, "/etc/nixos/configuration.nix")

    if diff or args.upgrade:
        print(f"Rebuilding NixOS on {node.name}")
        if args.upgrade:
            channel_cmd = f"nix-channel --add https://nixos.org/channels/{cluster.nix_channel} nixos"
            stdin, stdout, stderr = node.ssh.exec_command(channel_cmd)
            if stdout.channel.recv_exit_status() != 0:
                print(stdout.read().decode())
                print(stderr.read().decode())
                raise RuntimeError
            nixos_cmd = f"nixos-rebuild {args.nixos_action} --upgrade"
        else:
            nixos_cmd = f"nixos-rebuild {args.nixos_action}"
        stdin, stdout, stderr = node.ssh.exec_command(nixos_cmd)

        if stdout.channel.recv_exit_status() != 0:
            print(stdout.read().decode())
            print(stderr.read().decode())
            with node.sftp.open("/etc/nixos/configuration.nix", "w") as remote_file:
                remote_file.write(remote_config_str)
            print(f"`nixos-rebuild` failed on {node.name}.  Changes reverted")
            raise RuntimeError()
        else:
            if args.verbose:
                print(stdout.read().decode())
                print(stderr.read().decode())
            if args.nixos_action == "boot":
                print(f"Draining {node.name}")
                stdin, stdout, stderr = node.ssh.exec_command(
                    f"kubectl drain {node.name} --ignore-daemonsets --delete-emptydir-data"
                )
                if stdout.channel.recv_exit_status() != 0:
                    print(stdout.read().decode())
                    print(stderr.read().decode())
                    raise RuntimeError()
                if args.verbose:
                    print(stdout.read().decode())
                    print(stderr.read().decode())
                print(f"Rebooting {node.name}")
                # if we just reboot, the first reconnect attempt may erroneously
                # succeed before the box has actually shut down
                node.ssh.exec_command("systemctl stop sshd && reboot")
            node.sftp.close()
            node.ssh.close()
            node.ssh_ready()
            cluster.k8s_ready()
            if args.nixos_action == "boot":
                stdin, stdout, stderr = node.ssh.exec_command(
                    f"kubectl uncordon {node.name}"
                )
                if stdout.channel.recv_exit_status() != 0:
                    print(stdout.read().decode())
                    print(stderr.read().decode())
                    raise RuntimeError()
                print(f"{node.name} uncordoned")
            cluster.ceph_ready()
            cluster.daemonsets_ready("kube-system")
            cluster.daemonsets_ready("default")
            cluster.deployments_ready("default")
            cluster.deployments_ready("kube-system")
    else:
        print(colored("No action needed on {}".format(node.name), "green"))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("-i", "--inventory", default="inventory.yaml")
    parser.add_argument("-n", "--nixos-action", default="boot")
    parser.add_argument("-u", "--upgrade", action="store_true")
    parser.add_argument("--skip-initial-health", action="store_true")
    parser.add_argument("-v", "--verbose", action="store_true")
    parser.add_argument("-d", "--disruption-budget", type=int)
    args = parser.parse_args()

    if args.nixos_action != "boot" and args.nixos_action != "switch":
        raise AssertionError("--nixos-action must be one of boot, switch")

    cluster = Cluster.from_yaml(args.inventory)

    try:
        os.mkdir("artifacts")
    except FileExistsError:
        pass

    if not args.skip_initial_health:
        cluster.k8s_ready()
        cluster.ceph_ready()
        cluster.daemonsets_ready("kube-system")
        cluster.daemonsets_ready("default")
        cluster.deployments_ready("default")
        cluster.deployments_ready("kube-system")

    if args.disruption_budget:
        disruption_budget = args.disruption_budget
    else:
        disruption_budget = len(cluster.nodes) // 2

    with ThreadPoolExecutor(max_workers=disruption_budget) as pool:
        futures = {pool.submit(reconcile, n, cluster, args): n for n in cluster.nodes}
        for future in as_completed(futures):
            try:
                result = future.result()
                if result:
                    print(result)
            except Exception:
                traceback.print_exc()
                sys.exit(1)


if __name__ == "__main__":
    sys.exit(main())
