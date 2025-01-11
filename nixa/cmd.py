import sys
import yaml
import argparse
from os import mkdir

from group import Group


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
