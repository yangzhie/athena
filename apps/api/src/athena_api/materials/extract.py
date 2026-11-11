"""Attributable extraction, with no macros or external document references executed."""
import re
import shutil
import subprocess
import zipfile
from pathlib import Path
from xml.etree import ElementTree as ET


class ExtractionError(ValueError):
    pass


def validate(path: Path, suffix: str):
    with path.open('rb') as stream:
        head = stream.read(64)
    if suffix == '.pdf' and head[:5] != b'%PDF-':
        raise ExtractionError('The file is not a valid PDF.')
    if suffix not in {'.pdf', '.txt', '.md', '.docx', '.pptx'}:
        signatures = (head.startswith((b'RIFF', b'ID3', b'fLaC', b'OggS', b'\x1aE\xdf\xa3', b'\xff\xfb', b'\xff\xf3', b'\xff\xf2'))
                      or head[4:8] in {b'ftyp', b'moov', b'wide', b'mdat'})
        if not signatures:
            raise ExtractionError('The recording does not contain a supported audio/video container.')
    if suffix in {'.docx', '.pptx'}:
        try:
            with zipfile.ZipFile(path) as archive:
                names = archive.namelist()
                required = 'word/document.xml' if suffix == '.docx' else 'ppt/presentation.xml'
                if required not in names or sum(i.file_size for i in archive.infolist()) > 40 * 1024 * 1024:
                    raise ExtractionError('Invalid or excessively expanded Office document.')
        except zipfile.BadZipFile:
            raise ExtractionError('The file is not a valid Office document.') from None
    if suffix in {'.txt', '.md'}:
        try:
            text = path.read_text(encoding='utf-8')
            if '\x00' in text or not text.strip():
                raise ValueError()
        except (ValueError, UnicodeError):
            raise ExtractionError('Text files must contain nonempty UTF-8 text.') from None


def _parts(text):
    # Bound passages while retaining the exact text and its page/slide/section.
    return [text[start:start + 1500] for start in range(0, len(text), 1500) if text[start:start + 1500].strip()]


def extract(path: Path, suffix: str):
    validate(path, suffix)
    located = []
    if suffix in {'.txt', '.md'}:
        located = [(None, 'Text', path.read_text(encoding='utf-8'))]
    elif suffix == '.pdf':
        if not shutil.which('pdftotext'):
            raise ExtractionError('PDF extraction is unavailable: install Poppler (pdftotext).')
        try:
            output = subprocess.run(['pdftotext', '-layout', str(path), '-'], capture_output=True, timeout=45, check=True).stdout.decode('utf-8')
        except (subprocess.SubprocessError, UnicodeError):
            raise ExtractionError('PDF text extraction failed. The PDF may be encrypted or damaged.') from None
        located = [(i + 1, None, text) for i, text in enumerate(output.split('\f')) if text.strip()]
        if not located:
            raise ExtractionError('This PDF has no extractable text. OCR is required and is not configured.')
    else:
        with zipfile.ZipFile(path) as archive:
            names = ['word/document.xml'] if suffix == '.docx' else sorted(
                [n for n in archive.namelist() if re.fullmatch(r'ppt/slides/slide[0-9]+\.xml', n)],
                key=lambda n: int(re.search(r'slide([0-9]+)\.xml', n).group(1)))
            for name in names:
                try:
                    root = ET.fromstring(archive.read(name))
                except ET.ParseError:
                    raise ExtractionError('Office document contains malformed XML.') from None
                if suffix == '.docx':
                    paragraphs = [''.join(node.itertext()) for node in root.iter() if node.tag.endswith('}p')]
                    # DOCX pages depend on layout; never invent page numbers.
                    located.extend((None, f'Paragraph {i + 1}', text) for i, text in enumerate(paragraphs) if text.strip())
                else:
                    slide = int(re.search(r'slide([0-9]+)\.xml', name).group(1))
                    text = '\n'.join(node.text for node in root.iter() if node.tag.endswith('}t') and node.text)
                    located.append((slide, f'Slide {slide}', text))
    passages = [(page, section, part) for page, section, text in located for part in _parts(text)]
    if not passages:
        raise ExtractionError('The document contains no extractable text.')
    return passages
