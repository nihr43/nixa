apply: lint
  nix-shell --run 'python3 nixa'

upgrade: lint
  nix-shell --run 'python3 nixa -u'

reboot: lint
  nix-shell --run 'python3 nixa --reboot'

test:
  nix-shell --run 'cd tests; python3 test_main.py'

lint:
  black .
  flake8 . --ignore=E501,W503

req: lint
  nix-shell --run 'pip freeze > requirements.txt'
