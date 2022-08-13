import typing
import tempfile
import subprocess
import pathlib
import shutil
import os.path
import json
from dataclasses import dataclass

import yaml

TMODLOADER_GAME_ID = "1281930"

@dataclass
class ModSpec:
    workshop_id: int
    enabled: bool
    version: typing.Optional[str]


@dataclass
class ModSpecPack:
    output: str
    mods: typing.List[ModSpec]

    @classmethod
    def from_file(cls, filename):
        with open(filename) as fd:
            parsed = yaml.safe_load(fd)

        output_path = parsed.get("output", "./Mods")
        parsed_mods = parsed.get("mods", [])
        mods = []
        pack = cls(output=output_path, mods=mods)

        for idx, mod in enumerate(parsed_mods):
            workshop_id = mod.get("id", None)

            if not workshop_id:
                raise Exception(f"Missing id on mod #{idx}")

            enabled = mod.get("enabled", True)
            version = mod.get("version", None)

            mods.append(ModSpec(workshop_id, enabled, version))

        return pack


def main():
    mod_spec_pack = ModSpecPack.from_file('mod-config.yaml')
    enabled = set()

    with tempfile.TemporaryDirectory() as tmpdir:
        root_path = pathlib.Path(tmpdir)

        for mod in mod_spec_pack.mods:
            if not mod.enabled:
                continue

            # steamcmd +force_install_dir $PWD/../tmod +login anonymous +workshop_download_item 1281930 $MOD_ID +quit
            subprocess.check_call(
                [
                    "steamcmd",
                    "+force_install_dir",
                    tmpdir,
                    "+login",
                    "anonymous",
                    "+workshop_download_item",
                    TMODLOADER_GAME_ID,
                    str(mod.workshop_id),
                    "+quit",
                ],
                stdout=subprocess.DEVNULL,
            )

            mod_path = root_path / "steamapps" / "workshop" / "content" / TMODLOADER_GAME_ID / str(mod.workshop_id)
            subdirs = [x.name for x in mod_path.iterdir() if x.is_dir()]
            version = None

            if mod.version:
                if not mod.version in subdirs:
                    raise Exception(f"Version {mod.version} is not present for mod {mod.workshop_id}")

                version = mod.version
            else:
                if len(subdirs) > 1:
                    def sortable_subdir(subdir):
                        x, y = subdir.split(".")
                        return (int(x), int(y))

                    subdirs.sort(key=sortable_subdir)

                version = subdirs[-1]

            versioned_path = mod_path / version
            mod_files = list(versioned_path.glob("*.tmod"))

            if len(mod_files) != 1:
                raise Exception(f"Expected exactly one .tmod file in {versioned_path}")

            shutil.copy(mod_files[0].as_posix(), os.path.join(mod_spec_pack.output, mod_files[0].name))
            enabled.add(os.path.splitext(mod_files[0].name)[0])

    with open(os.path.join(mod_spec_pack.output, "enabled.json"), "w") as fd:
        json.dump(sorted(enabled), fd)
