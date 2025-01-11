import sys
import difflib
from io import StringIO
from invoke.exceptions import UnexpectedExit
from termcolor import colored
from jinja2 import Environment, FileSystemLoader
from concurrent.futures import ThreadPoolExecutor

from host import Host


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
