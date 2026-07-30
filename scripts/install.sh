#!/usr/bin/env sh
set -eu

repository_root=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
python_bin=${PYTHON:-python3}
source_path=${1:-"$repository_root/pet"}

cd "$repository_root"
"$python_bin" -m rin_pet validate "$source_path" --strict
"$python_bin" -m rin_pet install --source "$source_path"
