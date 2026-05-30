"""Unit tests for _oe.OERunner."""

import os
import subprocess
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from pyoe._oe import OERunner
from pyoe.exceptions import OEConfigError, OERuntimeError


class TestOERunnerInit:
    def test_uses_dlc_env_var(self, tmp_path):
        progres = tmp_path / "bin" / "_progres"
        progres.parent.mkdir(parents=True)
        progres.touch()
        with patch.dict(os.environ, {"DLC": str(tmp_path)}):
            runner = OERunner()
            assert runner.dlc == tmp_path

    def test_explicit_dlc_overrides_env(self, tmp_path):
        progres = tmp_path / "bin" / "_progres"
        progres.parent.mkdir(parents=True)
        progres.touch()
        with patch.dict(os.environ, {"DLC": "/wrong/path"}):
            runner = OERunner(dlc=str(tmp_path))
            assert runner.dlc == tmp_path

    def test_raises_if_progres_missing(self, tmp_path):
        with pytest.raises(OEConfigError):
            OERunner(dlc=str(tmp_path))


class TestOERunnerBaseEnv:
    def _make_runner(self, tmp_path):
        (tmp_path / "bin").mkdir()
        (tmp_path / "bin" / "_progres").touch()
        (tmp_path / "tty").mkdir()
        return OERunner(dlc=str(tmp_path))

    def test_dlc_in_env(self, tmp_path):
        runner = self._make_runner(tmp_path)
        env = runner._base_env()
        assert env["DLC"] == str(tmp_path)

    def test_tty_in_propath(self, tmp_path):
        runner = self._make_runner(tmp_path)
        env = runner._base_env()
        assert str(tmp_path / "tty") in env["PROPATH"].split(":")

    def test_term_defaults_to_xterm_when_unset(self, tmp_path):
        runner = self._make_runner(tmp_path)
        env_without_term = {k: v for k, v in os.environ.items() if k != "TERM"}
        with patch.dict(os.environ, env_without_term, clear=True):
            env = runner._base_env()
            assert env.get("TERM") == "xterm"

    def test_protermcap_points_to_oe_file(self, tmp_path):
        runner = self._make_runner(tmp_path)
        env_without_protermcap = {k: v for k, v in os.environ.items() if k != "PROTERMCAP"}
        with patch.dict(os.environ, env_without_protermcap, clear=True):
            env = runner._base_env()
            assert env.get("PROTERMCAP") == str(tmp_path / "protermcap")


class TestOERunnerRunBin:
    def _make_runner(self, tmp_path):
        (tmp_path / "bin").mkdir()
        (tmp_path / "bin" / "_progres").touch()
        (tmp_path / "bin" / "procopy").touch()
        return OERunner(dlc=str(tmp_path))

    def test_raises_on_nonzero_rc(self, tmp_path):
        runner = self._make_runner(tmp_path)
        mock_result = MagicMock()
        mock_result.returncode = 1
        mock_result.stderr = "some error"
        mock_result.stdout = ""

        with patch("subprocess.run", return_value=mock_result):
            with pytest.raises(OERuntimeError) as exc_info:
                runner.run_bin("procopy", ["/a", "/b"])
            assert exc_info.value.returncode == 1

    def test_returns_completed_process_on_success(self, tmp_path):
        runner = self._make_runner(tmp_path)
        mock_result = MagicMock()
        mock_result.returncode = 0

        with patch("subprocess.run", return_value=mock_result) as mock_run:
            result = runner.run_bin("procopy", ["/a", "/b"])
            assert result.returncode == 0
