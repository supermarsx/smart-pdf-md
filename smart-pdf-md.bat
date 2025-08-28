@echo off
rem ---------------------------------------------------------
rem smart-pdf-md.bat
rem Batch entry point for smart PDF->Markdown conversion.
rem - Validates toolchain (python/pip)
rem - Ensures deps (pymupdf, marker-pdf if needed)
rem - Exposes CLI flags mapping to environment knobs
rem - Emits and runs a Python driver for routing/slicing
rem ---------------------------------------------------------
setlocal EnableExtensions EnableDelayedExpansion
chcp 65001 >nul
set "RC=0"

echo =========================================================
echo [boot] smart_pdf_md.bat starting...
echo =========================================================

rem ===== Args =====
set "INPUT=%~1"
if "%INPUT%"=="" set "INPUT=%cd%"
set "SLICE=%~2"
if "%SLICE%"=="" set "SLICE=40"

rem Parse optional flags after INPUT and SLICE (map to env vars)
set "_IN=%~1"
set "_SL=%~2"
shift
shift
:parse_flags
if "%~1"=="" goto :flags_done
if /I "%~1"=="--mode"          ( set "SMART_PDF_MD_MODE=%~2" & shift & shift & goto :parse_flags )
if /I "%~1"=="--out"           ( set "SMART_PDF_MD_OUTPUT_DIR=%~2" & shift & shift & goto :parse_flags )
if /I "%~1"=="--images"        ( set "SMART_PDF_MD_IMAGES=1" & shift & goto :parse_flags )
if /I "%~1"=="--no-images"     ( set "SMART_PDF_MD_IMAGES=0" & shift & goto :parse_flags )
if /I "%~1"=="--min-chars"     ( set "SMART_PDF_MD_TEXT_MIN_CHARS=%~2" & shift & shift & goto :parse_flags )
if /I "%~1"=="--min-ratio"     ( set "SMART_PDF_MD_TEXT_MIN_RATIO=%~2" & shift & shift & goto :parse_flags )
if /I "%~1"=="--mock"          ( set "SMART_PDF_MD_MARKER_MOCK=1" & shift & goto :parse_flags )
if /I "%~1"=="--mock-fail"     ( set "SMART_PDF_MD_MARKER_MOCK=1" & set "SMART_PDF_MD_MARKER_MOCK_FAIL=1" & shift & goto :parse_flags )
rem Unrecognized flag: skip it and continue
shift
goto :parse_flags
:flags_done
set "INPUT=%_IN%"
set "SLICE=%_SL%"

echo [cfg ] Input            : "%INPUT%"
echo [cfg ] Slice pages      : %SLICE%
echo [cfg ] Output format    : markdown
rem Derive image extraction status from env/flags (default 0)
set "_IMG=%SMART_PDF_MD_IMAGES%"
if "%_IMG%"=="" set "_IMG=0"
set "_IMG_STATUS=DISABLED"
if "%_IMG%"=="1" set "_IMG_STATUS=ENABLED"
echo [cfg ] Image extraction : %_IMG_STATUS%
echo [cfg ] DPI (low/high)   : 96 / 120
set "MODE=%SMART_PDF_MD_MODE%"
if "%MODE%"=="" set "MODE=auto"
echo [cfg ] Mode             : %MODE%
if not "%SMART_PDF_MD_OUTPUT_DIR%"=="" echo [cfg ] Output dir       : %SMART_PDF_MD_OUTPUT_DIR%
if not "%SMART_PDF_MD_IMAGES%"=="" echo [cfg ] Images            : %SMART_PDF_MD_IMAGES%
if not "%SMART_PDF_MD_TEXT_MIN_CHARS%"=="" echo [cfg ] Heur min chars  : %SMART_PDF_MD_TEXT_MIN_CHARS%
if not "%SMART_PDF_MD_TEXT_MIN_RATIO%"=="" echo [cfg ] Heur min ratio  : %SMART_PDF_MD_TEXT_MIN_RATIO%

rem ===== Toolchain =====
where python >nul 2>&1 || (echo [FATAL] Python not found on PATH & set RC=1 & goto :the_end)
python -m pip --version >nul 2>&1 || (echo [FATAL] pip not available & set RC=1 & goto :the_end)
for /f "usebackq tokens=1,2" %%A in (`python -c "import sys,struct;print(sys.version.split()[0],str(struct.calcsize('P')*8))"`) do (
  echo [lint] Python OK       : %%A / %%B-bit
)
for /f "usebackq tokens=*" %%A in (`python -m pip --version`) do echo [lint] pip OK          : %%A

rem ===== Deps =====
echo [deps] Checking PyMuPDF...
python -c "import importlib.util,sys;sys.exit(0 if importlib.util.find_spec('fitz') else 1)"
if errorlevel 1 (
  echo [deps] Installing PyMuPDF ...
  python -m pip install -q pymupdf || (echo [FATAL] pip install pymupdf failed & set RC=1 & goto :the_end)
) else (
  echo [deps] PyMuPDF present.
)

if /I not "%MODE%"=="fast" (
  echo [deps] Checking marker-pdf...
  python -c "import importlib.util,sys;sys.exit(0 if importlib.util.find_spec('marker') else 1)"
  if errorlevel 1 (
    echo [deps] Installing marker-pdf ...
    python -m pip install -q marker-pdf || (echo [FATAL] pip install marker-pdf failed & set RC=1 & goto :the_end)
  ) else (
    echo [deps] marker-pdf present.
  )
)

rem ===== Env for Marker (optional) =====
if /I not "%MODE%"=="fast" (
  set "TORCH_DEVICE=cuda"
  set "OCR_ENGINE=surya"
  set "PYTORCH_CUDA_ALLOC_CONF=garbage_collection_threshold:0.8,max_split_size_mb:64,expandable_segments:False"
  echo [env ] TORCH_DEVICE=%TORCH_DEVICE%
  echo [env ] OCR_ENGINE=%OCR_ENGINE%
  echo [env ] PYTORCH_CUDA_ALLOC_CONF=%PYTORCH_CUDA_ALLOC_CONF%
) else (
  echo [env ] Marker environment skipped (MODE=fast)
)

rem ===== Write Python driver =====
set "PYDRV=%TEMP%\smart_pdf_md_driver.py"
echo [io  ] Writing driver: "%PYDRV%"
rem Avoid CMD delayed expansion interfering with Python f-strings like {e!r}
setlocal DisableDelayedExpansion
type nul > "%PYDRV%"
>>"%PYDRV%" echo import sys, os, subprocess, shutil, tempfile, time
>>"%PYDRV%" echo from pathlib import Path
>>"%PYDRV%" echo import fitz
>>"%PYDRV%" echo.
>>"%PYDRV%" echo LOWRES=96; HIGHRES=120
>>"%PYDRV%" echo MODE=os.environ.get('SMART_PDF_MD_MODE','auto').lower()
>>"%PYDRV%" echo MOCK=os.environ.get('SMART_PDF_MD_MARKER_MOCK','0')=='1'
>>"%PYDRV%" echo MOCK_FAIL=os.environ.get('SMART_PDF_MD_MARKER_MOCK_FAIL','0')=='1'
>>"%PYDRV%" echo IMAGES=os.environ.get('SMART_PDF_MD_IMAGES','0')=='1'
>>"%PYDRV%" echo OUTDIR=os.environ.get('SMART_PDF_MD_OUTPUT_DIR')
>>"%PYDRV%" echo MIN_CHARS=int(os.environ.get('SMART_PDF_MD_TEXT_MIN_CHARS','100'))
>>"%PYDRV%" echo MIN_RATIO=float(os.environ.get('SMART_PDF_MD_TEXT_MIN_RATIO','0.2'))
>>"%PYDRV%" echo MOCK_FAIL_IF_SLICE_GT=int(os.environ.get('SMART_PDF_MD_MOCK_FAIL_IF_SLICE_GT','0'))
>>"%PYDRV%" echo.
>>"%PYDRV%" echo def log(msg): print(msg, flush=True)
>>"%PYDRV%" echo.
>>"%PYDRV%" echo def mock_write_markdown(pdf, outdir, note):
>>"%PYDRV%" echo ^    out = Path(outdir) / (Path(pdf).stem + '.md')
>>"%PYDRV%" echo ^    prev = out.read_text(encoding='utf-8') if out.exists() else ''
>>"%PYDRV%" echo ^    text = f'# MOCK MARKER OUTPUT\n{note}\nSource: {pdf}\n'
>>"%PYDRV%" echo ^    out.write_text(prev + ("\n\n" if prev else '') + text, encoding='utf-8')
>>"%PYDRV%" echo ^    return 0
>>"%PYDRV%" echo.
>>"%PYDRV%" echo def which_marker_single():
>>"%PYDRV%" echo ^    p = shutil.which('marker_single')
>>"%PYDRV%" echo ^    return [p] if p else [sys.executable, '-m', 'marker.scripts.convert_single']
>>"%PYDRV%" echo.
>>"%PYDRV%" echo def try_open(pdf):
>>"%PYDRV%" echo ^    try:
>>"%PYDRV%" echo ^        return fitz.open(pdf)
>>"%PYDRV%" echo ^    except Exception as e:
>>"%PYDRV%" echo ^        log(f'[WARN ] PyMuPDF cannot open: {e!r}')
>>"%PYDRV%" echo ^        return None
>>"%PYDRV%" echo.
>>"%PYDRV%" echo def is_textual(pdf, min_chars_per_page=MIN_CHARS, min_ratio=MIN_RATIO):
>>"%PYDRV%" echo ^    doc = try_open(pdf)
>>"%PYDRV%" echo ^    if not doc or len(doc)==0:
>>"%PYDRV%" echo ^        return False
>>"%PYDRV%" echo ^    text_pages = 0
>>"%PYDRV%" echo ^    for page in doc:
>>"%PYDRV%" echo ^        t = page.get_text('text')
>>"%PYDRV%" echo ^        if t and len(''.join(t.split())) ^>= min_chars_per_page:
>>"%PYDRV%" echo ^            text_pages += 1
>>"%PYDRV%" echo ^    return (text_pages / len(doc)) ^>= min_ratio
>>"%PYDRV%" echo.
>>"%PYDRV%" echo def convert_text(pdf, outdir):
>>"%PYDRV%" echo ^    t0 = time.perf_counter()
>>"%PYDRV%" echo ^    doc = fitz.open(pdf)
>>"%PYDRV%" echo ^    parts = [p.get_text('text') for p in doc]
>>"%PYDRV%" echo ^    out = Path(outdir) / (Path(pdf).stem + '.md')
>>"%PYDRV%" echo ^    out.write_text('\\n\\n'.join(parts), encoding='utf-8')
>>"%PYDRV%" echo ^    log(f'[TEXT ] {pdf} -> {out}  ({time.perf_counter()-t0:.2f}s)')
>>"%PYDRV%" echo.
>>"%PYDRV%" echo def marker_single_pass(pdf, outdir):
>>"%PYDRV%" echo ^    if MOCK:
>>"%PYDRV%" echo ^        if MOCK_FAIL:
>>"%PYDRV%" echo ^            return 1
>>"%PYDRV%" echo ^        return mock_write_markdown(pdf, outdir, 'mock marker single-pass')
>>"%PYDRV%" echo ^    ms = which_marker_single()
>>"%PYDRV%" echo ^    cmd = ms + [str(pdf),'--output_format','markdown']
>>"%PYDRV%" echo ^    if not IMAGES:
>>"%PYDRV%" echo ^        cmd += ['--disable_image_extraction']
>>"%PYDRV%" echo ^    cmd += ['--page_range','0-999999','--output_dir',str(outdir),'--lowres_image_dpi',str(LOWRES),'--highres_image_dpi',str(HIGHRES)]
>>"%PYDRV%" echo ^    log(f'[RUN  ] {" ".join(cmd)}')
>>"%PYDRV%" echo ^    return subprocess.run(cmd).returncode
>>"%PYDRV%" echo.
>>"%PYDRV%" echo def marker_slice(pdf, outdir, start, end):
>>"%PYDRV%" echo ^    if MOCK:
>>"%PYDRV%" echo ^        if MOCK_FAIL or (MOCK_FAIL_IF_SLICE_GT and (end-start+1) ^> MOCK_FAIL_IF_SLICE_GT):
>>"%PYDRV%" echo ^            return 1
>>"%PYDRV%" echo ^        return mock_write_markdown(pdf, outdir, f'mock marker slice {start}-{end}')
>>"%PYDRV%" echo ^    ms = which_marker_single()
>>"%PYDRV%" echo ^    cmd = ms + [str(pdf),'--output_format','markdown']
>>"%PYDRV%" echo ^    if not IMAGES:
>>"%PYDRV%" echo ^        cmd += ['--disable_image_extraction']
>>"%PYDRV%" echo ^    cmd += ['--page_range',f'{start}-{end}','--output_dir',str(outdir),'--lowres_image_dpi',str(LOWRES),'--highres_image_dpi',str(HIGHRES)]
>>"%PYDRV%" echo ^    log(f'[RUN  ] {" ".join(cmd)}')
>>"%PYDRV%" echo ^    return subprocess.run(cmd).returncode
>>"%PYDRV%" echo.
>>"%PYDRV%" echo def marker_convert(pdf, outdir, slice_pages):
>>"%PYDRV%" echo ^    doc = try_open(pdf)
>>"%PYDRV%" echo ^    if not doc:
>>"%PYDRV%" echo ^        rc = marker_single_pass(pdf, outdir)
>>"%PYDRV%" echo ^        if rc!=0:
>>"%PYDRV%" echo ^            log(f'[ERROR] marker_single rc={rc}')
>>"%PYDRV%" echo ^            return 3
>>"%PYDRV%" echo ^        log('[OK   ] single-pass done')
>>"%PYDRV%" echo ^        return 0
>>"%PYDRV%" echo ^    total = len(doc)
>>"%PYDRV%" echo ^    start = 0
>>"%PYDRV%" echo ^    cur = int(slice_pages)
>>"%PYDRV%" echo ^    log(f'[MRK_S] total_pages={total} slice={cur} dpi={LOWRES}/{HIGHRES}')
>>"%PYDRV%" echo ^    while start ^< total:
>>"%PYDRV%" echo ^        end = min(start+cur-1, total-1)
>>"%PYDRV%" echo ^        t0 = time.perf_counter()
>>"%PYDRV%" echo ^        rc = marker_slice(pdf, outdir, start, end)
>>"%PYDRV%" echo ^        dt = time.perf_counter()-t0
>>"%PYDRV%" echo ^        if rc!=0:
>>"%PYDRV%" echo ^            if cur ^<= 5:
>>"%PYDRV%" echo ^                log(f'[ERROR] slice {start}-{end} failed rc={rc} (min slice)')
>>"%PYDRV%" echo ^                return 2
>>"%PYDRV%" echo ^            cur = max(5, cur//2)
>>"%PYDRV%" echo ^            log(f'[WARN ] retry with slice={cur}')
>>"%PYDRV%" echo ^            continue
>>"%PYDRV%" echo ^        log(f'[OK   ] pages {start}-{end} in {dt:.2f}s')
>>"%PYDRV%" echo ^        start = end+1
>>"%PYDRV%" echo ^    return 0
>>"%PYDRV%" echo.
>>"%PYDRV%" echo def process_one(pdf, idx, total, slice_pages):
>>"%PYDRV%" echo ^    pdf = Path(pdf)
>>"%PYDRV%" echo ^    outdir = Path(OUTDIR) if OUTDIR else pdf.parent
>>"%PYDRV%" echo ^    outdir.mkdir(parents=True, exist_ok=True)
>>"%PYDRV%" echo ^    log('='*64)
>>"%PYDRV%" echo ^    log(f'[file ] ({idx}/{total}) {pdf}')
>>"%PYDRV%" echo ^    try:
>>"%PYDRV%" echo ^        if MODE == 'fast':
>>"%PYDRV%" echo ^            log('[path ] FORCED FAST -> PyMuPDF')
>>"%PYDRV%" echo ^            convert_text(str(pdf), str(outdir))
>>"%PYDRV%" echo ^            return 0
>>"%PYDRV%" echo ^        if MODE == 'marker':
>>"%PYDRV%" echo ^            log('[path ] FORCED MARKER -> marker_single')
>>"%PYDRV%" echo ^            return marker_convert(str(pdf), str(outdir), slice_pages)
>>"%PYDRV%" echo ^        if is_textual(str(pdf)):
>>"%PYDRV%" echo ^            log('[path ] TEXTUAL -> fast PyMuPDF')
>>"%PYDRV%" echo ^            convert_text(str(pdf), str(outdir))
>>"%PYDRV%" echo ^            return 0
>>"%PYDRV%" echo ^        log('[path ] NON-TEXTUAL -> marker_single')
>>"%PYDRV%" echo ^        return marker_convert(str(pdf), str(outdir), slice_pages)
>>"%PYDRV%" echo ^    except Exception as e:
>>"%PYDRV%" echo ^        log(f'[FALL ] unhandled error: {e!r}')
>>"%PYDRV%" echo ^        return 9
>>"%PYDRV%" echo.
>>"%PYDRV%" echo def main():
>>"%PYDRV%" echo ^    if len(sys.argv) ^< 3:
>>"%PYDRV%" echo ^        log('[USAGE] smart_pdf_md_driver.py INPUT SLICE')
>>"%PYDRV%" echo ^        sys.exit(2)
>>"%PYDRV%" echo ^    inp = Path(sys.argv[1])
>>"%PYDRV%" echo ^    slice_pages = int(sys.argv[2])
>>"%PYDRV%" echo ^    if inp.exists() and inp.is_dir():
>>"%PYDRV%" echo ^        files = sorted([p for p in inp.rglob('*.pdf')])
>>"%PYDRV%" echo ^        log(f'[scan ] folder: {inp}  files={len(files)}')
>>"%PYDRV%" echo ^    elif inp.exists():
>>"%PYDRV%" echo ^        files = [inp]
>>"%PYDRV%" echo ^        log(f'[scan ] single file: {inp}')
>>"%PYDRV%" echo ^    else:
>>"%PYDRV%" echo ^        log(f'[ERROR] input not found: {inp}')
>>"%PYDRV%" echo ^        sys.exit(1)
>>"%PYDRV%" echo ^    t0 = time.perf_counter()
>>"%PYDRV%" echo ^    fails = 0
>>"%PYDRV%" echo ^    exit_code = 0
>>"%PYDRV%" echo ^    for i, f in enumerate(files, 1):
>>"%PYDRV%" echo ^        try:
>>"%PYDRV%" echo ^            rc = process_one(f, i, len(files), slice_pages)
>>"%PYDRV%" echo ^        except Exception as e:
>>"%PYDRV%" echo ^            log(f'[CRASH] {f}: {e!r}')
>>"%PYDRV%" echo ^            rc = 10
>>"%PYDRV%" echo ^        if rc != 0:
>>"%PYDRV%" echo ^            fails += 1
>>"%PYDRV%" echo ^            if exit_code == 0:
>>"%PYDRV%" echo ^                exit_code = rc
>>"%PYDRV%" echo ^    log(f'[DONE ] total={len(files)} failures={fails} elapsed={time.perf_counter()-t0:.2f}s')
>>"%PYDRV%" echo ^    sys.exit(exit_code)
>>"%PYDRV%" echo.
>>"%PYDRV%" echo if __name__ == '__main__': main()

endlocal

if errorlevel 1 (echo [FATAL] Failed to write driver & goto :the_end)
for %%A in ("%PYDRV%") do set "DRV_SIZE=%%~zA"
echo [io  ] Driver size: %DRV_SIZE% bytes

rem ===== Lint driver before running (pure CMD) =====
echo [lint] py_compile driver ...
python -c "import py_compile, sys; py_compile.compile(r'%PYDRV%', doraise=True)"
if errorlevel 1 (
  echo [FATAL] Driver failed to compile. See Python error above.
  set RC=1
  goto :the_end
) else (
  echo [lint] OK
)


rem ===== Preview head (pure CMD) =====
for /f "usebackq tokens=1* delims=:" %%A in (`findstr /n /r "^" "%PYDRV%"`) do (
  if %%A LEQ 8 echo [head] %%B
)

rem ===== Run driver =====
echo [run ] python "%PYDRV%" "%INPUT%" %SLICE%
python "%PYDRV%" "%INPUT%" %SLICE%
set "RC=%ERRORLEVEL%"
echo [exit] Driver returned %RC%

:the_end
echo =========================================================
echo [done] smart_pdf_md.bat finished.
echo =========================================================
exit /b %RC%
