apply: lint
  nix-shell --run 'python3 nixa'

upgrade: lint
  nix-shell --run 'python3 nixa -u'

reboot: lint
  nix-shell --run 'python3 nixa --reboot'

test: lint
  nix-shell --run 'python3 tests/test_main.py'
  nix-shell --run 'python3 nixa -i artifacts/test_inventory.yaml --skip-initial --private-key private.key'

lint:
  black .
  flake8 . --ignore=E501,W503

req: lint
  nix-shell --run 'pip freeze > requirements.txt'
