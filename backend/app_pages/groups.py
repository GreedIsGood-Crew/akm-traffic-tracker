# akm-traffic-tracker/backend/app_pages/groups.py

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from typing import Optional, List
from sqlalchemy.orm import Session
from sqlalchemy import text
from db import get_db
from datetime import datetime

router = APIRouter()

# ====== Pydantic Models ======

class GroupCreate(BaseModel):
    name: str
    type: str = "campaign"  # campaign, offer, landing, traffic_source
    color: Optional[str] = "#6366f1"
    description: Optional[str] = None

class GroupUpdate(BaseModel):
    name: Optional[str] = None
    type: Optional[str] = None
    color: Optional[str] = None
    description: Optional[str] = None

class GroupResponse(BaseModel):
    id: int
    name: str
    type: str
    color: str
    description: Optional[str]
    created_at: datetime
    items_count: int = 0

# ====== GET /groups ======
@router.get("/")
async def get_groups(
    type: Optional[str] = Query(None, description="Filter by type: campaign, offer, landing, traffic_source"),
    db: Session = Depends(get_db)
):
    """Get all groups with item counts."""
    
    type_filter = f"WHERE g.type = '{type}'" if type else ""
    
    query = text(f"""
        SELECT 
            g.id, g.name, g.type::text, g.color, g.description, g.created_at,
            CASE g.type::text
                WHEN 'campaign' THEN (SELECT COUNT(*) FROM campaigns c WHERE c.group_id = g.id)
                WHEN 'offer' THEN (SELECT COUNT(*) FROM offers o WHERE o.group_id = g.id)
                WHEN 'landing' THEN (SELECT COUNT(*) FROM landings l WHERE l.group_id = g.id)
                WHEN 'traffic_source' THEN (SELECT COUNT(*) FROM sources s WHERE s.group_id = g.id)
                ELSE 0
            END as items_count
        FROM groups g
        {type_filter}
        ORDER BY g.name
    """)
    
    result = db.execute(query)
    rows = result.fetchall()
    
    return [
        {
            "id": row.id,
            "name": row.name,
            "type": row.type,
            "color": row.color or "#6366f1",
            "description": row.description,
            "created_at": row.created_at.isoformat() if row.created_at else None,
            "items_count": row.items_count or 0
        }
        for row in rows
    ]

# ====== GET /groups/{id} ======
@router.get("/{group_id}")
async def get_group(group_id: int, db: Session = Depends(get_db)):
    """Get single group by ID."""
    
    query = text("SELECT * FROM groups WHERE id = :id")
    result = db.execute(query, {"id": group_id})
    row = result.fetchone()
    
    if not row:
        raise HTTPException(status_code=404, detail="Group not found")
    
    return {
        "id": row.id,
        "name": row.name,
        "type": row.type,
        "color": row.color,
        "description": row.description,
        "created_at": row.created_at.isoformat() if row.created_at else None
    }

# ====== POST /groups ======
@router.post("/")
async def create_group(group: GroupCreate, db: Session = Depends(get_db)):
    """Create new group."""
    
    query = text("""
        INSERT INTO groups (name, type, color, description)
        VALUES (:name, :type, :color, :description)
        RETURNING id
    """)
    
    try:
        result = db.execute(query, {
            "name": group.name,
            "type": group.type,
            "color": group.color,
            "description": group.description
        })
        db.commit()
        new_id = result.fetchone()[0]
        return {"message": "Group created", "id": new_id}
    except Exception as e:
        db.rollback()
        if "unique" in str(e).lower():
            raise HTTPException(status_code=400, detail="Group with this name already exists")
        raise HTTPException(status_code=500, detail=str(e))

# ====== PUT /groups/{id} ======
@router.put("/{group_id}")
async def update_group(group_id: int, group: GroupUpdate, db: Session = Depends(get_db)):
    """Update existing group."""
    
    updates = []
    params = {"id": group_id}
    
    if group.name is not None:
        updates.append("name = :name")
        params["name"] = group.name
    if group.type is not None:
        updates.append("type = :type")
        params["type"] = group.type
    if group.color is not None:
        updates.append("color = :color")
        params["color"] = group.color
    if group.description is not None:
        updates.append("description = :description")
        params["description"] = group.description
    
    if not updates:
        raise HTTPException(status_code=400, detail="No fields to update")
    
    updates.append("updated_at = NOW()")
    
    query = text(f"UPDATE groups SET {', '.join(updates)} WHERE id = :id")
    result = db.execute(query, params)
    db.commit()
    
    if result.rowcount == 0:
        raise HTTPException(status_code=404, detail="Group not found")
    
    return {"message": "Group updated"}

# ====== DELETE /groups/{id} ======
@router.delete("/{group_id}")
async def delete_group(group_id: int, db: Session = Depends(get_db)):
    """Delete group (sets group_id = NULL on related items)."""
    
    # Unlink items first
    db.execute(text("UPDATE campaigns SET group_id = NULL WHERE group_id = :id"), {"id": group_id})
    db.execute(text("UPDATE offers SET group_id = NULL WHERE group_id = :id"), {"id": group_id})
    db.execute(text("UPDATE sources SET group_id = NULL WHERE group_id = :id"), {"id": group_id})
    
    # Delete group
    result = db.execute(text("DELETE FROM groups WHERE id = :id"), {"id": group_id})
    db.commit()
    
    if result.rowcount == 0:
        raise HTTPException(status_code=404, detail="Group not found")
    
    return {"message": "Group deleted"}
