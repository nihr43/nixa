import sys
import difflib
import time
import fabric
import re
from invoke.exceptions import UnexpectedExit
from termcolor import colored
from paramiko.ssh_exception import NoValidConnectionsError, SSHException
from jinja2 import Environment, FileSystemLoader


class Host:
    def __init__(self, name, hostvars, templates):
        """
        'name' might be a ip or a hostname
        """
        self.name = name
        self.ssh_ready()
        self.hostvars = hostvars
        self.templates = templates

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
                    connect_timeout=1,
                    config=fabric.config.Config(overrides={"run": {"hide": True}}),
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

    def reconcile(self, args):
        file_loader = FileSystemLoader("modules/")
        env = Environment(loader=file_loader)
        changed = []
        print(colored(f"{self.name}:", "yellow"))

        for t in ["configuration.nix"] + self.templates:
            template = env.get_template(t)
            output = template.render(modules=self.templates, hostvars=self.hostvars)

            output_file_path = f"artifacts/{self.name}_{t}"
            with open(output_file_path, "w") as f:
                f.write(output)

            with open(output_file_path, "r") as local_file:
                local_config = local_file.read()

            diff = None
            created = None
            remote_config = None
            try:
                remote_config = self.ssh.run(f"cat /etc/nixos/{t}")

                diff = list(
                    difflib.unified_diff(
                        remote_config.stdout.splitlines(), local_config.splitlines()
                    )
                )
            except UnexpectedExit as e:
                if "No such file or directory" in str(e):
                    created = True
                    print(colored(f"{t} created", "yellow"))
                else:
                    raise NotImplementedError

            if diff:
                diff_formatted = colored("\n".join(diff), "yellow")
                print(diff_formatted)

            if diff or created:
                changed.append(t)
                self.ssh.put(local=output_file_path, remote=f"/etc/nixos/{t}")

        if len(changed) != 0:
            print(f"rebuilding NixOS on {self.name}")
            nixos_cmd = f"nixos-rebuild {args.action}"

            try:
                result = self.ssh.run(nixos_cmd)
            except UnexpectedExit as e:
                print(e)
                print(f"`nixos-rebuild` failed on {self.name}.")
                sys.exit(1)
            else:
                if args.verbose:
                    print(result.stdout)
                    print(result.stderr)

                if args.action == "boot":
                    self.reboot()
        else:
            print(colored("no action needed", "green"))

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
