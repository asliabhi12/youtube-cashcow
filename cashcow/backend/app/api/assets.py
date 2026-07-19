"""Overlay-asset routes: list, upload, and delete.

Assets are the images/videos an overlay composites onto the frame. The backend
owns the asset library, split into read-only bundled assets and deletable user
uploads (see ``app.services.assets``). A profile references an asset only by its
bare filename; the workflow adapter resolves that name to a filesystem path, so
the frontend never handles paths.

Only overlay assets exist today. The list endpoint accepts a ``type`` query
param (defaulting to ``overlay``) so the URL shape can grow to other asset kinds
without a breaking change; any other value returns an empty list rather than an
error.
"""

from fastapi import APIRouter, File, HTTPException, UploadFile, status

from app.services import assets

router = APIRouter(prefix="/assets", tags=["assets"])


@router.get("", response_model=list[assets.AssetSummary])
def list_assets(type: str = "overlay") -> list[assets.AssetSummary]:
    """Return overlay assets, built-ins first then user uploads.

    ``type`` selects the asset kind; only ``overlay`` is implemented, so any
    other value yields an empty list (forward-compatible, never an error).
    """
    if type != "overlay":
        return []
    return assets.list_assets()


@router.post(
    "/upload",
    response_model=assets.AssetSummary,
    status_code=status.HTTP_201_CREATED,
)
async def upload_asset(file: UploadFile = File(...)) -> assets.AssetSummary:
    """Store an uploaded overlay asset and return its summary.

    The service validates the extension, size, and filename; a validation
    failure maps to 422. The returned ``name`` is the (possibly de-duplicated)
    bare filename a profile should store.
    """
    data = await file.read()
    try:
        return assets.save_upload(file.filename or "", data)
    except assets.AssetValidationError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)
        ) from exc


@router.delete("/{name}", status_code=status.HTTP_204_NO_CONTENT)
def delete_asset(name: str) -> None:
    """Delete a user-uploaded overlay asset.

    Returns 403 for a built-in asset (read-only) and 404 if no user asset by
    that name exists.
    """
    try:
        assets.delete_asset(name)
    except assets.AssetReadOnlyError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc
    except assets.AssetNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
