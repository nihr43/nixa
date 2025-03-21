apply: lint
  nix-shell --run 'python3 nixa'

upgrade: lint
  nix-shell --run 'python3 nixa -u'

reboot: lint
  nix-shell --run 'python3 nixa --reboot'

test: lint
  nix-shell --run 'python3 e2e --cleanup --deploy --persist'
  nix-shell --run 'python3 nixa -i test-inventory.yaml -p2'
  nix-shell --run 'python3 nixa -i test-inventory.yaml --upgrade -p2 -a boot'
  nix-shell --run 'python3 e2e --cleanup'

lint:
  black .
  flake8 . --ignore=E501,W503

req: lint
  nix-shell --run 'pip freeze > requirements.txt'
