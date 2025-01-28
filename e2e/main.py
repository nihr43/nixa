import argparse
import os
from nixos_mock import Cluster, cleanup
from jinja2 import Environment, FileSystemLoader

base_dir = os.path.dirname(os.path.abspath(__file__))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("-p", "--persist", action="store_true")
    parser.add_argument("-c", "--cleanup", action="store_true")
    parser.add_argument("-d", "--deploy", action="store_true")
    args = parser.parse_args()

    key = "nixa-e2e"
    count = 2

    if args.cleanup:
        cleanup(key)

    if args.deploy:
        c = Cluster(key, count)  # noqa

        file_loader = FileSystemLoader(f"{base_dir}/src")
        env = Environment(loader=file_loader)
        template = env.get_template("test-inventory.yaml.j2")
        output = template.render(cluster=c)
        with open("test-inventory.yaml", "w") as f:
            f.write(output)

        if not args.persist:
            cleanup(key)


if __name__ == "__main__":
    main()
