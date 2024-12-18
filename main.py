import sys
import time
import yaml
import difflib
import uuid
import argparse
import ipaddress
import fabric
from os import mkdir
from io import StringIO
from invoke.exceptions import UnexpectedExit
from termcolor import colored
from jinja2 import Environment, FileSystemLoader
from paramiko.ssh_exception import NoValidConnectionsError


class Group:
    def __init__(self, name, hosts, templates, nix_channel):
        self.name = name
        self.templates = templates
        self.nix_channel = nix_channel
        self.hosts = [Host(h) for h in hosts]


class Host:
    def __init__(self, ip):
        self.ip = ip
        self.hostname = str(uuid.uuid5(uuid.NAMESPACE_OID, self.ip))
        self.ssh_ready()
        self.interface = self.get_interface()
        self.gateway = self.get_gateway()

    def get_interface(self):
        result = self.ssh.run("ip r get 1.1.1.1 | awk '/via/{print $5}'")
        interface = result.stdout.strip()
        if interface.startswith(("eth", "eno", "enp")):
            return interface
        else:
            raise NotImplementedError(interface)

    def get_gateway(self):
        result = self.ssh.run("ip r get 1.1.1.1 | awk '/via/{print $3}'")
        gw = result.stdout.strip()
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
                print("Waiting for {} to become reachable".format(self.name))
            try:
                self.ssh = fabric.Connection(
                    host=self.ip,
                    user="root",
                    config=fabric.config.Config(overrides={"run": {"hide": True}}),
                )
                self.ssh.run("hostname")
                print("{} is reachable".format(self.hostname))
                return
            except (TimeoutError, EOFError, NoValidConnectionsError):
                time.sleep(1)
                continue

        raise TimeoutError

    def reboot(self):
        print(f"Rebooting {self.hostname}")
        # if we just reboot, the first reconnect attempt may erroneously
        # succeed before the box has actually shut down
        self.ssh.run("systemctl stop sshd && reboot")
        time.sleep(10)
        self.ssh.close()
        self.ssh_ready()


def reconcile(group, args):
    print(
        colored(
            f"applying template {group.templates[0]} to {[n.hostname for n in group.hosts]}",
            "yellow",
        )
    )
    file_loader = FileSystemLoader("templates/")
    env = Environment(loader=file_loader)

    for node in group.hosts:
        template = env.get_template(group.templates[0])
        output = template.render(attrs=node)

        output_file_path = "artifacts/{}".format(node.hostname)
        with open(output_file_path, "w") as f:
            f.write(output)

        with open(output_file_path, "r") as local_file:
            local_config = local_file.read()

        remote_config = node.ssh.run("cat /etc/nixos/configuration.nix").stdout

        diff = list(
            difflib.unified_diff(remote_config.splitlines(), local_config.splitlines())
        )

        if diff:
            print("{} modified:".format(node.hostname))
            diff_formatted = colored("\n".join(diff), "yellow")
            print(diff_formatted)
            node.ssh.put(local=output_file_path, remote="/etc/nixos/configuration.nix")

        if diff or args.upgrade:
            print(f"Rebuilding NixOS on {node.hostname}")
            if args.upgrade:
                result = node.ssh.run("uname -r")
                initial_kernel = result.stdout.strip()
                channel_cmd = f"nix-channel --add https://nixos.org/channels/{group.nix_channel} nixos"
                try:
                    node.ssh.run(channel_cmd)
                except UnexpectedExit as e:
                    print(e)
                    sys.exit(1)
                nixos_cmd = f"nixos-rebuild {args.nixos_action} --upgrade"
            else:
                nixos_cmd = f"nixos-rebuild {args.nixos_action}"

            try:
                result = node.ssh.run(nixos_cmd)
            except UnexpectedExit as e:
                # if rebuild faild, write the original back
                membuf = StringIO(remote_config)
                node.ssh.put(membuf, remote="/etc/nixos/configuration.nix")
                print(e)
                print(f"`nixos-rebuild` failed on {node.hostname}.  Changes reverted.")
                sys.exit(1)
            else:
                if args.verbose:
                    print(result.stdout)
                    print(result.stderr)

                no_action = """unpacking channels...
building Nix...
building the system configuration...
updating GRUB 2 menu...
"""

                if args.upgrade and result.stderr == no_action:
                    print(colored(f"No upgrade needed on {node.hostname}", "green"))
                    return
                if args.nixos_action == "boot":
                    node.reboot()
                if args.upgrade:
                    result = node.ssh.run("uname -r")
                    final_kernel = result.stdout.strip()
                    if final_kernel != initial_kernel:
                        print(
                            colored(
                                f"Kernel upgraded from {initial_kernel} to {final_kernel} on {node.hostname}",
                                "yellow",
                            )
                        )
        else:
            print(colored("No action needed on {}".format(node.hostname), "green"))


def parse_inventory(inventory: str) -> [Group]:
    groups = []
    with open(inventory, "r") as f:
        yam = yaml.safe_load(f)
        for group, values in yam.items():
            groups.append(
                Group(
                    group, values["hosts"], values["templates"], values["nix-channel"]
                )
            )
    return groups


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("-i", "--inventory", default="inventory.yaml")
    parser.add_argument("-n", "--nixos-action", default="boot")
    parser.add_argument("-u", "--upgrade", action="store_true")
    parser.add_argument("--skip-initial-health", action="store_true")
    parser.add_argument("-v", "--verbose", action="store_true")
    parser.add_argument("--private-key", type=str)
    parser.add_argument("-r", "--reboot", action="store_true")
    args = parser.parse_args()

    if args.nixos_action != "boot" and args.nixos_action != "switch":
        raise AssertionError("--nixos-action must be one of boot, switch")

    try:
        mkdir("artifacts")
    except FileExistsError:
        pass

    groups = parse_inventory(args.inventory)

    for g in groups:
        reconcile(g, args)


if __name__ == "__main__":
    sys.exit(main())
