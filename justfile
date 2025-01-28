apply: lint
  nix-shell --run 'python3 nixa'

upgrade: lint
  nix-shell --run 'python3 nixa -u'

reboot: lint
  nix-shell --run 'python3 nixa --reboot'

test: lint
  nix-shell --run 'cd e2e; python3 main.py --persist'
  nix-shell --run 'python3 nixa -i e2e/test-inventory.yaml -p2'
  nix-shell --run 'python3 nixa -i e2e/test-inventory.yaml --upgrade -p2 -a boot'

lint:
  black .
  flake8 . --ignore=E501,W503

req: lint
  nix-shell --run 'pip freeze > requirements.txt'
