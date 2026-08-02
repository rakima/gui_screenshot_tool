import threading

from gui_screenshot_tool.gui import run_in_background


def test_background_work_does_not_block_caller():
    release = threading.Event()
    started = threading.Event()

    def work():
        started.set()
        release.wait(timeout=2)

    worker = run_in_background(work, "test-worker")

    assert started.wait(timeout=1)
    assert worker.is_alive()
    release.set()
    worker.join(timeout=1)
    assert not worker.is_alive()
