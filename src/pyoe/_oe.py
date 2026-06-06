"""Low-level OpenEdge subprocess runner."""

from __future__ import annotations

import os
import subprocess
import tempfile
from pathlib import Path
from typing import Optional, Sequence

from .exceptions import OEConfigError, OERuntimeError

# ABL batch programs embedded as strings.  Each receives its runtime parameter
# via SESSION:PARAMETER (passed with -param on the command line) or a hardcoded
# comma-delimited string for multi-value cases.

_ABL_DUMP_DF = """\
/* pyoe: dump full schema to .df file */
/* SESSION:PARAMETER = tables|outfile|codepage */
DEFINE VARIABLE cTables   AS CHARACTER NO-UNDO INITIAL "ALL".
DEFINE VARIABLE cOutFile  AS CHARACTER NO-UNDO.
DEFINE VARIABLE cCodePage AS CHARACTER NO-UNDO INITIAL ?.
ASSIGN
    cTables   = ENTRY(1, SESSION:PARAMETER, "|")
    cOutFile  = ENTRY(2, SESSION:PARAMETER, "|")
    cCodePage = ENTRY(3, SESSION:PARAMETER, "|") NO-ERROR.
IF cTables   = "" OR cTables   = ? THEN cTables   = "ALL".
IF cCodePage = "" THEN cCodePage = ?.
RUN prodict/dump_df.p (INPUT cTables, INPUT cOutFile, INPUT cCodePage).
"""

_ABL_DUMP_INC = """\
/* pyoe: incremental dump (delta) – DICTDB vs DICTDB2.
   DICTDB  = the DESIRED schema (first -db arg; what you want the target to become).
   DICTDB2 = the CURRENT database (connected inside ABL; what you have now).
   Delta = statements to apply to DICTDB2 to make it match DICTDB.
   SESSION:PARAMETER = current_db_path|outfile|codepage */
DEFINE VARIABLE cCurrentDb AS CHARACTER NO-UNDO.
DEFINE VARIABLE cOutFile   AS CHARACTER NO-UNDO.
DEFINE VARIABLE cCodePage  AS CHARACTER NO-UNDO INITIAL ?.
DEFINE VARIABLE hdump      AS HANDLE    NO-UNDO.
ASSIGN
    cCurrentDb = ENTRY(1, SESSION:PARAMETER, "|")
    cOutFile   = ENTRY(2, SESSION:PARAMETER, "|")
    cCodePage  = ENTRY(3, SESSION:PARAMETER, "|") NO-ERROR.
IF cCodePage = "" THEN cCodePage = ?.

CONNECT VALUE(cCurrentDb) -ld DICTDB2 -1 NO-ERROR.
IF ERROR-STATUS:ERROR THEN DO:
    MESSAGE "pyoe dump_inc: CONNECT DICTDB2 failed:" ERROR-STATUS:GET-MESSAGE(1).
    RETURN.
END.

RUN prodict/dump_inc.p PERSISTENT SET hdump NO-ERROR.
IF ERROR-STATUS:ERROR THEN DO:
    MESSAGE "pyoe dump_inc: persistent handle failed:" ERROR-STATUS:GET-MESSAGE(1).
    DISCONNECT DICTDB2.
    RETURN.
END.

RUN setFileName  IN hdump (INPUT cOutFile)  NO-ERROR.
IF cCodePage <> ? THEN
    RUN setCodePage  IN hdump (INPUT cCodePage) NO-ERROR.
RUN setIndexMode IN hdump (INPUT TRUE)      NO-ERROR.

RUN doDumpIncr IN hdump NO-ERROR.
IF ERROR-STATUS:ERROR THEN
    MESSAGE "pyoe dump_inc: doDumpIncr failed:" ERROR-STATUS:GET-MESSAGE(1).

DELETE OBJECT hdump NO-ERROR.
DISCONNECT DICTDB2.
"""

_ABL_LOAD_DF = """\
/* pyoe: load a .df schema file into the connected database */
DEFINE VARIABLE cInFile AS CHARACTER NO-UNDO.
cInFile = SESSION:PARAMETER.
RUN prodict/load_df.p (INPUT cInFile).
"""


class OERunner:
    """Wraps OpenEdge batch (`_progres -1 -b`) invocations.

    Parameters
    ----------
    dlc:
        Path to the OpenEdge installation directory.  Defaults to the
        ``DLC`` environment variable, then ``/usr/dlc``.
    """

    def __init__(self, dlc: Optional[str] = None) -> None:
        self.dlc = Path(dlc or os.environ.get("DLC", "/usr/dlc"))
        self._validate()

    # ------------------------------------------------------------------
    # Public helpers
    # ------------------------------------------------------------------

    def run_abl(
        self,
        abl: str,
        db_paths: Sequence[str | Path],
        param: str = "",
        extra_env: Optional[dict] = None,
        timeout: int = 120,
    ) -> subprocess.CompletedProcess:
        """Write *abl* to a temp file and execute it in batch mode.

        Parameters
        ----------
        abl:
            ABL source code for the startup procedure.
        db_paths:
            Databases to connect, in order.  The first is DICTDB; the
            second (if any) is DICTDB2.
        param:
            Value passed as ``SESSION:PARAMETER`` inside the procedure.
        extra_env:
            Additional environment variables to merge.
        timeout:
            Process timeout in seconds.
        """
        with tempfile.NamedTemporaryFile(suffix=".p", mode="w", delete=False) as fh:
            fh.write(abl)
            proc_path = fh.name

        try:
            return self._run(
                proc_path=proc_path,
                db_paths=db_paths,
                param=param,
                extra_env=extra_env,
                timeout=timeout,
            )
        finally:
            try:
                os.unlink(proc_path)
            except OSError:
                pass

    def run_bin(
        self,
        binary: str,
        args: Sequence[str],
        timeout: int = 60,
        extra_env: Optional[dict] = None,
    ) -> subprocess.CompletedProcess:
        """Run an OE utility binary (e.g. prostrct, procopy) directly."""
        exe = self.dlc / "bin" / binary
        if not exe.exists():
            exe = Path("/usr/bin") / binary
        cmd = [str(exe)] + [str(a) for a in args]
        env = self._base_env()
        if extra_env:
            env.update(extra_env)
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            env=env,
            timeout=timeout,
        )
        if result.returncode != 0:
            raise OERuntimeError(
                f"{binary} failed (rc={result.returncode}): {result.stderr.strip()}",
                returncode=result.returncode,
                stderr=result.stderr,
                stdout=result.stdout,
            )
        return result

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    @property
    def cpstream(self) -> str:
        """Return the -cpstream value from $DLC/startup.pf, or '' if absent."""
        pf = self.dlc / "startup.pf"
        try:
            for line in pf.read_text().splitlines():
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                parts = line.split()
                if len(parts) >= 2 and parts[0] == "-cpstream":
                    return parts[1]
        except OSError:
            pass
        return ""

    def _validate(self) -> None:
        progres = self.dlc / "bin" / "_progres"
        if not progres.exists():
            raise OEConfigError(
                f"OpenEdge runtime not found at {progres}. "
                "Set DLC to your installation directory."
            )

    def _base_env(self) -> dict:
        env = dict(os.environ)
        env["DLC"] = str(self.dlc)
        # PROPATH must include tty so prodict/*.r can be found inside prodict.pl
        existing_propath = env.get("PROPATH", "")
        tty = str(self.dlc / "tty")
        if tty not in existing_propath.split(":"):
            env["PROPATH"] = f"{tty}:{existing_propath}" if existing_propath else tty
        # OE requires a terminal type present in its own PROTERMCAP; "dumb" is not.
        env.setdefault("PROTERMCAP", str(self.dlc / "protermcap"))
        env.setdefault("TERM", "xterm")
        return env

    def _run(
        self,
        proc_path: str,
        db_paths: Sequence[str | Path],
        param: str,
        extra_env: Optional[dict],
        timeout: int,
    ) -> subprocess.CompletedProcess:
        progres = str(self.dlc / "bin" / "_progres")
        cmd = [progres]
        for db in db_paths:
            cmd.extend(["-db", str(db)])
        cmd.extend(["-1", "-b", "-p", proc_path])
        if param:
            cmd.extend(["-param", param])

        env = self._base_env()
        if extra_env:
            env.update(extra_env)

        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            env=env,
            timeout=timeout,
        )
        if result.returncode != 0:
            raise OERuntimeError(
                f"OpenEdge batch process failed (rc={result.returncode}):\n"
                f"{result.stderr.strip()}",
                returncode=result.returncode,
                stderr=result.stderr,
                stdout=result.stdout,
            )
        return result
