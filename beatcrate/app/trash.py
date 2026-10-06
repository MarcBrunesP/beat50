"""Moving files to the Mac's Trash, so a deleted selection can be put back from there (Finder's "Put Back")."""
from ..errors import BeatcrateError


def move(path):
    """Moves a file to the Trash; BeatcrateError("trash_failed") if the Mac refuses."""
    from Foundation import NSFileManager, NSURL  # Cocoa, imported here so the rest of the app does not need it

    ok, _, error = NSFileManager.defaultManager().trashItemAtURL_resultingItemURL_error_(
        NSURL.fileURLWithPath_(str(path)), None, None)
    if not ok:
        detail = str(error.localizedDescription()) if error is not None else path.name
        raise BeatcrateError("trash_failed", f"Could not move it to the Trash: {detail}", detail=detail)
