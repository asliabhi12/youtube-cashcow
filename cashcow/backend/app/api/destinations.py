"""Destination CRUD routes."""

from fastapi import APIRouter, HTTPException, status

from app.models.destination import Destination, DestinationInput
from app.services import destinations

router = APIRouter(prefix="/destinations", tags=["destinations"])


@router.get("", response_model=list[Destination])
def list_destinations() -> list[Destination]:
    return destinations.list_destinations()


@router.post("", response_model=Destination, status_code=status.HTTP_201_CREATED)
def create_destination(payload: DestinationInput) -> Destination:
    return destinations.create_destination(payload)


@router.put("/{destination_id}", response_model=Destination)
def update_destination(destination_id: str, payload: DestinationInput) -> Destination:
    try:
        return destinations.update_destination(destination_id, payload)
    except destinations.DestinationNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Destination not found") from exc


@router.delete("/{destination_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_destination(destination_id: str) -> None:
    try:
        destinations.delete_destination(destination_id)
    except destinations.DestinationNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Destination not found") from exc

