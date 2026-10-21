"""Check that online storage replaces offline hooks without losing the workbook."""
import runpy
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]

def test_online_build_has_cloud_hooks_and_retains_examples():
    offline=ROOT/'NGSL_NAWL_10天学习词表.html'
    before=offline.read_bytes()
    runpy.run_path(str(ROOT/'server/build_web.py'),run_name='__main__')
    page=(ROOT/'server/web/index.html').read_text()
    assert 'cloud.boot(' in page
    assert 'cloud.setWord(' in page
    assert 'cloud.importWords(' in page
    assert "progress=validProgress(p.words)" not in page
    assert 'localStorage.getItem(KEY)' not in page
    assert 'sense-translation' in page and 'translateSelection' in page
    assert 'examples-data' in page and 'lookup-data' in page
    assert 'createSpeaker(' in page and 'id="rate-btn"' in page
    assert 'id="theme-btn"' in page and ':root[data-theme=dark]' in page and 'prefers-color-scheme:dark' in page
    assert '/account' in page and '/assets/cloud.js' in page
    assert offline.read_bytes()==before
    assert "if(!cloud.ready){toast('正在读取账号进度，请稍候');return;}download(" in page
