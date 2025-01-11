import sys
import time
import yaml
import difflib
import argparse
import fabric
import re
from os import mkdir
from io import StringIO
from invoke.exceptions import UnexpectedExit
from termcolor import colored
from jinja2 import Environment, FileSystemLoader
from paramiko.ssh_exception import NoValidConnectionsError, SSHException
from concurrent.futures import ThreadPoolExecutor


class Group:
    def __init__(self, name, hosts, templates, nix_channel):
        self.name = name
        self.templates = templates
        self.nix_channel = nix_channel

        self.hosts = []
        for h, hostvars in hosts.items():
            self.hosts.append(Host(h, hostvars))

    def upgrade(self, args):
        print(colored(f"{self.name}:", "magenta"))
        with ThreadPoolExecutor(max_workers=args.parallel) as pool:
            {pool.submit(h.upgrade, args, self.nix_channel): h for h in self.hosts}

    def reconcile(self, args):
        print(
            colored(
                f"applying template {self.templates[0]} to {self.name}: {[n.name for n in self.hosts]}",
                "magenta",
            )
        )
        file_loader = FileSystemLoader("templates/")
        env = Environment(loader=file_loader)

        for node in self.hosts:
            print(colored(f"{node.name}:", "yellow"))
            template = env.get_template(self.templates[0])
            output = template.render(attrs=node, hostvars=node.hostvars)

            output_file_path = "artifacts/{}".format(node.name)
            with open(output_file_path, "w") as f:
                f.write(output)

            with open(output_file_path, "r") as local_file:
                local_config = local_file.read()

            remote_config = node.ssh.run("cat /etc/nixos/configuration.nix").stdout

            diff = list(
                difflib.unified_diff(
                    remote_config.splitlines(), local_config.splitlines()
                )
            )

            if diff:
                diff_formatted = colored("\n".join(diff), "yellow")
                print(diff_formatted)
                node.ssh.put(
                    local=output_file_path, remote="/etc/nixos/configuration.nix"
                )

                print(f"rebuilding NixOS on {node.name}")
                nixos_cmd = f"nixos-rebuild {args.action}"

                try:
                    result = node.ssh.run(nixos_cmd)
                except UnexpectedExit as e:
                    # if rebuild faild, write the original back
                    membuf = StringIO(remote_config)
                    node.ssh.put(membuf, remote="/etc/nixos/configuration.nix")
                    print(e)
                    print(f"`nixos-rebuild` failed on {node.name}.  Changes reverted.")
                    sys.exit(1)
                else:
                    if args.verbose:
                        print(result.stdout)
                        print(result.stderr)

                    if args.action == "boot":
                        node.reboot()
            else:
                print(colored("no action needed", "green"))


class Host:
    def __init__(self, name, hostvars):
        """
        'name' might be a ip or a hostname
        """
        self.name = name
        self.ssh_ready()
        self.hostvars = hostvars

    def ssh_ready(self):
        i = 0
        while i < 300:
            i += 1
            if i % 10 == 0:
                print("Waiting for {} to become reachable".format(self.name))
            try:
                self.ssh = fabric.Connection(
                    host=self.name,
                    user="root",
                    config=fabric.config.Config(
                        overrides={"run": {"hide": True}, "connect_timeout": 1}
                    ),
                )
                self.ssh.run("hostname")
                print("{} is reachable".format(self.name))
                return
            except (
                TimeoutError,
                EOFError,
                NoValidConnectionsError,
                SSHException,
            ):
                time.sleep(1)
                continue

        raise TimeoutError

    def reboot(self):
        print(f"Rebooting {self.name}")
        # if we just reboot, the first reconnect attempt may erroneously
        # succeed before the box has actually shut down
        self.ssh.run("systemctl stop sshd && reboot")
        time.sleep(10)
        self.ssh.close()
        self.ssh_ready()

    def upgrade(self, args, nix_channel):
        result = self.ssh.run("uname -r")
        initial_kernel = result.stdout.strip()
        print(colored(f"upgrading {self.name}:", "yellow"))
        print(f"enforcing nixos channel {nix_channel}")
        channel_cmd = (
            f"nix-channel --add https://nixos.org/channels/{nix_channel} nixos"
        )
        try:
            self.ssh.run(channel_cmd)
        except UnexpectedExit as e:
            print(e)
            sys.exit(1)

        nixos_cmd = f"nixos-rebuild {args.action} --upgrade"
        try:
            result = self.ssh.run(nixos_cmd)
        except UnexpectedExit as e:
            print(e)
            print(f"`nixos-rebuild {args.action} --upgrade` failed on {self.name}.")
            sys.exit(1)
        else:
            if args.verbose:
                print(result.stdout)
                print(result.stderr)

        paths_fetched_match = re.search(
            r"these (\d+) paths will be fetched", result.stderr
        )
        if paths_fetched_match:
            num_paths = paths_fetched_match.group(1)
            print(colored(f"{num_paths} paths fetched", "green"))

        derivations_built_match = re.search(
            r"these (\d+) derivations will be built", result.stderr
        )
        if derivations_built_match:
            num_paths = derivations_built_match.group(1)
            print(colored(f"{num_paths} derivations built", "green"))

        if not paths_fetched_match and not derivations_built_match:
            print(colored(f"no upgrades needed on {self.name}", "green"))
            return

        if args.action == "boot":
            self.reboot()

            result = self.ssh.run("uname -r")
            final_kernel = result.stdout.strip()
            if final_kernel != initial_kernel:
                print(
                    colored(
                        f"kernel upgraded from {initial_kernel} to {final_kernel} on {self.name}",
                        "yellow",
                    )
                )


def parse_inventory(inventory: str, limit: str) -> [Group]:
    groups = []
    with open(inventory, "r") as f:
        yam = yaml.safe_load(f)
        if not limit:
            for group, values in yam.items():
                groups.append(
                    Group(
                        group,
                        values["hosts"],
                        values["templates"],
                        values["nix-channel"],
                    )
                )
            return groups
        else:
            for group, values in yam.items():
                if group in limit:
                    groups.append(
                        Group(
                            group,
                            values["hosts"],
                            values["templates"],
                            values["nix-channel"],
                        )
                    )
            return groups


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("-i", "--inventory", default="inventory.yaml")
    parser.add_argument("-n", "--action", default="switch")
    parser.add_argument("-u", "--upgrade", action="store_true")
    parser.add_argument("-v", "--verbose", action="store_true")
    parser.add_argument("-r", "--reboot", action="store_true")
    parser.add_argument("--private-key", type=str)
    parser.add_argument("--limit", type=str)
    parser.add_argument("-p", "--parallel", type=int, default=1)
    args = parser.parse_args()

    if args.action != "boot" and args.action != "switch":
        raise AssertionError("--action must be one of boot, switch")

    try:
        mkdir("artifacts")
    except FileExistsError:
        pass

    groups = parse_inventory(args.inventory, args.limit)

    for g in groups:
        if args.upgrade:
            g.upgrade(args)
        else:
            g.reconcile(args)


if __name__ == "__main__":
    sys.exit(main())
