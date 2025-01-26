apply: lint
  nix-shell --run 'python3 nixa'

upgrade: lint
  nix-shell --run 'python3 nixa -u'

reboot: lint
  nix-shell --run 'python3 nixa --reboot'

test: lint
  nix-shell --run 'cd e2e; python3 main.py'

lint:
  black .
  flake8 . --ignore=E501,W503

req: lint
  nix-shell --run 'pip freeze > requirements.txt'
