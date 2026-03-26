# WeChat Dialog Tools

Utilities for working with local WeChat desktop data:

- `export_wechat_csv.py`: export merged WeChat messages into per-chat CSV files
- `prepare_persona_analysis.py`: build a GPT-ready persona analysis package from exported message data

## Setup

This project was developed with Python 3.13 on Windows.

Recommended steps:

```powershell
python -m venv .venv_pywxdump
.\.venv_pywxdump\Scripts\python -m pip install pywxdump
```

## Export CSV

```powershell
.\.venv_pywxdump\Scripts\python .\export_wechat_csv.py `
  --msg-db .\out\merged\merged_MSG.db `
  --contact-db .\out\core_dec\de_MicroMsg.db `
  --out-dir .\out\csv_export
```

## Prepare Persona Analysis Inputs

```powershell
.\.venv_pywxdump\Scripts\python .\prepare_persona_analysis.py `
  --msg-db .\out\merged\merged_MSG.db `
  --contact-db .\out\core_dec\de_MicroMsg.db `
  --out-dir .\out\persona_analysis
```

## Notes

- The generated `out/` directory is intentionally ignored by git.
- Local decrypted databases and exported chat data should be treated as sensitive.
