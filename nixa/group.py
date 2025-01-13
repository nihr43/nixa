import traceback
from termcolor import colored
from concurrent.futures import ThreadPoolExecutor, as_completed

from host import Host


class Group:
    def __init__(self, name, hosts, templates, nix_channel):
        self.name = name
        self.templates = templates
        self.nix_channel = nix_channel

        def create_host(args):
            h, hostvars = args
            return Host(h, hostvars, self.templates)

        with ThreadPoolExecutor() as pool:
            self.hosts = list(pool.map(create_host, hosts.items()))

    def upgrade(self, args):
        print(colored(f"{self.name}:", "magenta"))
        with ThreadPoolExecutor(max_workers=args.parallel) as pool:
            futures = {
                pool.submit(h.upgrade, args, self.nix_channel): h for h in self.hosts
            }

        for future in as_completed(futures):
            try:
                future.result()
            except Exception:
                traceback.print_exc()

    def reconcile(self, args):
        print(
            colored(
                f"applying modules {self.templates} to {self.name}: {[n.name for n in self.hosts]}",
                "magenta",
            )
        )
        with ThreadPoolExecutor(max_workers=args.parallel) as pool:
            futures = {pool.submit(h.reconcile, args): h for h in self.hosts}

        for future in as_completed(futures):
            try:
                future.result()
            except Exception:
                traceback.print_exc()
