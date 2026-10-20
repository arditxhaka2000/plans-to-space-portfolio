"""Versioned, bounded data contract. Coordinates are metres, Y up; no executable input."""
import math
from typing import Annotated, Literal
from pydantic import BaseModel, ConfigDict, Field, model_validator
from shapely.geometry import Polygon

Number = Annotated[float, Field(ge=-10000, le=10000, allow_inf_nan=False)]
Positive = Annotated[float, Field(gt=0, le=10000, allow_inf_nan=False)]
Id = Annotated[str, Field(min_length=1, max_length=160, pattern=r'^[A-Za-z0-9_./:-]+$')]
Vec2 = tuple[Number, Number]
Vec3 = tuple[Number, Number, Number]
Kind = Literal['wall','window','door','roof','slab','column','railing','solar panel','other']

class Data(BaseModel):
    model_config = ConfigDict(extra='forbid')

class Evidence(Data):
    pages: list[Annotated[int, Field(ge=1, le=100000)]] = Field(min_length=1, max_length=32)
    status: Literal['printed','measured','interpreted','estimated']
    reference: str = Field(min_length=1, max_length=1000)

class Material(Data):
    id: Id
    color: tuple[Annotated[float, Field(ge=0, le=1, allow_inf_nan=False)], Annotated[float, Field(ge=0, le=1, allow_inf_nan=False)], Annotated[float, Field(ge=0, le=1, allow_inf_nan=False)], Annotated[float, Field(ge=0, le=1, allow_inf_nan=False)]]

class Element(Data):
    id: Id
    material: Id
    evidence: Evidence

class Box(Element):
    kind: Kind
    center: Vec3
    size: tuple[Positive, Positive, Positive]

class Level(Data):
    id: Id
    elevation: Number

class Volume(Element):
    footprint: list[Vec2] = Field(min_length=3, max_length=128)
    level: Id
    height: Positive
    slabThickness: Positive = .26

class Roof(Element):
    vertices: list[Vec3] = Field(min_length=3, max_length=128)

class Opening(Data):
    id: Id
    kind: Literal['window','door']
    offset: Positive
    sill: Annotated[float, Field(ge=0, le=10000, allow_inf_nan=False)]
    width: Positive
    height: Positive
    frame: Positive = .04
    material: Id
    frameMaterial: Id
    evidence: Evidence

class Wall(Element):
    start: Vec2
    end: Vec2
    base: Number
    height: Positive
    thickness: Positive
    openings: list[Opening] = Field(default_factory=list, max_length=64)

class Group(Data):
    id: Id
    name: str = Field(min_length=1, max_length=200)
    members: list[Id] = Field(min_length=1, max_length=10000)

class Recipe(Data):
    schemaVersion: Literal['1.0']
    label: str = Field(min_length=1, max_length=200)
    interpretation: Literal['manually-interpreted','automatically-interpreted']
    units: Literal['metres']
    axes: Literal['X-right,Y-up,Z-plan-down']
    sourceDocumentHash: str = Field(pattern=r'^[a-fA-F0-9]{64}$')
    assumptions: list[Annotated[str, Field(max_length=2000)]] = Field(min_length=1, max_length=100)
    unresolved: list[Annotated[str, Field(max_length=2000)]] = Field(max_length=100)
    materials: list[Material] = Field(min_length=1, max_length=64)
    levels: list[Level] = Field(min_length=1, max_length=200)
    volumes: list[Volume] = Field(default_factory=list, max_length=500)
    walls: list[Wall] = Field(default_factory=list, max_length=5000)
    roofs: list[Roof] = Field(default_factory=list, max_length=500)
    boxes: list[Box] = Field(default_factory=list, max_length=20000)
    groups: list[Group] = Field(default_factory=list, max_length=5000)

    @model_validator(mode='after')
    def geometry(self):
        elements=[*self.boxes,*self.volumes,*self.walls,*self.roofs]
        openings=[o for w in self.walls for o in w.openings]
        ids=[e.id for e in [*elements,*openings]]
        if len(ids)!=len(set(ids)): raise ValueError('Duplicate component IDs')
        for values in [self.materials,self.levels,self.groups]:
            if len({v.id for v in values})!=len(values): raise ValueError('Duplicate definition IDs')
        mats={m.id for m in self.materials}; levels={l.id for l in self.levels}
        if any(e.material not in mats for e in [*elements,*openings]) or any(o.frameMaterial not in mats for o in openings): raise ValueError('Unknown material')
        if any(v.level not in levels for v in self.volumes): raise ValueError('Unknown level')
        for v in self.volumes:
            p=Polygon(v.footprint)
            if not p.is_valid or p.area<.0001: raise ValueError('Invalid footprint')
        for r in self.roofs:
            p=Polygon([(v[0],v[2]) for v in r.vertices])
            if not p.is_valid or p.area<.0001: raise ValueError('Roof must have a valid plan projection')
            a,b,c=r.vertices[:3];u=[b[i]-a[i] for i in range(3)];v=[c[i]-a[i] for i in range(3)];n=[u[1]*v[2]-u[2]*v[1],u[2]*v[0]-u[0]*v[2],u[0]*v[1]-u[1]*v[0]]
            if abs(n[1])<1e-8 or any(abs(sum(n[i]*(q[i]-a[i]) for i in range(3)))>1e-5*math.sqrt(sum(x*x for x in n)) for q in r.vertices): raise ValueError('Roof must be planar')
        for w in self.walls:
            length=math.dist(w.start,w.end)
            if length<.01: raise ValueError('Zero length wall')
            for i,o in enumerate(w.openings):
                if o.offset-o.width/2<0 or o.offset+o.width/2>length+1e-7 or o.sill+o.height>w.height+1e-7 or o.frame*2>=min(o.width,o.height): raise ValueError('Opening/frame outside wall')
                for b in w.openings[:i]:
                    if abs(o.offset-b.offset)<(o.width+b.width)/2 and o.sill<b.sill+b.height and b.sill<o.sill+o.height: raise ValueError('Overlapping openings')
        if len(elements)-len(self.walls)+len(openings)*5+sum(4 if len(w.openings)==1 else (len(w.openings)*2+1)**2-len(w.openings) for w in self.walls)>45000: raise ValueError('Geometry complexity exceeds 45000 parts')
        known=set(ids)
        if any(m not in known for g in self.groups for m in g.members): raise ValueError('Unknown group member')
        if sum(len(g.members) for g in self.groups)>100000 or any(len(set(g.members))!=len(g.members) for g in self.groups): raise ValueError('Excessive or duplicate group membership')
        return self

def read_recipe(path):
    from pathlib import Path
    p=Path(path)
    if p.stat().st_size>12_000_000: raise ValueError('Recipe exceeds 12 MB')
    return Recipe.model_validate_json(p.read_bytes())
