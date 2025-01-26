from nixos_mock import Cluster, cleanup


def main():
    key = "nixa-e2e"
    count = 2

    cleanup(key)
    c = Cluster(key, count)  # noqa
    cleanup(key)


if __name__ == "__main__":
    main()
