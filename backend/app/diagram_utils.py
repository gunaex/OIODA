"""Generates drawio-compatible mxGraphModel XML for the auto-diagram
features (ERD from live SQLAlchemy schema, state diagrams from
workflow_definitions.py). Layout is a plain grid — good enough to see the
whole picture at a glance; the user repositions boxes by hand in the
Whiteboard editor after generating, same as any other whiteboard."""
from xml.sax.saxutils import escape, quoteattr

TABLE_WIDTH = 220
HEADER_HEIGHT = 30
ROW_HEIGHT = 26
TABLES_PER_ROW = 3
H_GAP = 60
V_GAP = 60

STATE_WIDTH = 160
STATE_HEIGHT = 50
STATES_PER_ROW = 4
STATE_H_GAP = 80
STATE_V_GAP = 80


def _sanitize_id(*parts: str) -> str:
    raw = "_".join(parts)
    return "".join(c if c.isalnum() else "_" for c in raw)


def _vertex(cell_id, value, x, y, width, height, style, parent="1"):
    return (
        f'<mxCell id={quoteattr(cell_id)} value={quoteattr(value)} style={quoteattr(style)} '
        f'vertex="1" parent={quoteattr(parent)}>'
        f'<mxGeometry x="{x}" y="{y}" width="{width}" height="{height}" as="geometry" /></mxCell>'
    )


def _edge(edge_id, source, target, label=""):
    return (
        f'<mxCell id={quoteattr(edge_id)} value={quoteattr(label)} '
        f'style="edgeStyle=orthogonalEdgeStyle;rounded=0;html=1;endArrow=block;" '
        f'edge="1" parent="1" source={quoteattr(source)} target={quoteattr(target)}>'
        f'<mxGeometry relative="1" as="geometry" /></mxCell>'
    )


def _wrap(body: str) -> str:
    return (
        '<mxGraphModel dx="800" dy="600" grid="1" gridSize="10" guides="1" tooltips="1" '
        'connect="1" arrows="1" fold="1" page="1" pageScale="1" pageWidth="1400" '
        'pageHeight="1600" math="0" shadow="0"><root><mxCell id="0" />'
        f'<mxCell id="1" parent="0" />{body}</root></mxGraphModel>'
    )


def generate_erd_xml(sections: list[tuple[str, "MetaData"]]) -> str:
    """`sections` is a list of (label, sqlalchemy.MetaData) — e.g. Master DB
    and a project's own DB — rendered as separate labeled groups stacked
    vertically, since they're physically separate SQLite files with no
    real cross-file foreign keys (see the comment on
    ResourceAllocation.project_slug in models.py)."""
    cells = []
    edges = []
    table_cell_id = {}  # table name -> mxCell id, for wiring FK edges after all boxes exist
    y_cursor = 40

    for label, metadata in sections:
        tables = sorted(metadata.tables.values(), key=lambda t: t.name)
        if not tables:
            continue

        cells.append(
            _vertex(
                _sanitize_id("hdr", label),
                label,
                40,
                y_cursor,
                600,
                24,
                "text;fontStyle=1;fontSize=16;align=left;",
            )
        )
        y_cursor += 34

        for row_start in range(0, len(tables), TABLES_PER_ROW):
            row = tables[row_start : row_start + TABLES_PER_ROW]
            row_height = max(HEADER_HEIGHT + ROW_HEIGHT * max(len(t.columns), 1) for t in row)

            for col_idx, table in enumerate(row):
                cell_id = _sanitize_id("tbl", label, table.name)
                table_cell_id[table.name] = cell_id
                x = 40 + col_idx * (TABLE_WIDTH + H_GAP)
                box_height = HEADER_HEIGHT + ROW_HEIGHT * max(len(table.columns), 1)
                cells.append(
                    _vertex(
                        cell_id,
                        table.name,
                        x,
                        y_cursor,
                        TABLE_WIDTH,
                        box_height,
                        f"swimlane;fontStyle=1;align=center;startSize={HEADER_HEIGHT};",
                    )
                )
                for i, column in enumerate(table.columns):
                    prefix = "PK  " if column.primary_key else ""
                    col_label = f"{prefix}{column.name}: {column.type}"
                    style = "text;align=left;verticalAlign=middle;spacingLeft=6;"
                    if column.primary_key:
                        style += "fontStyle=1;"
                    cells.append(
                        _vertex(
                            f"{cell_id}_col_{i}",
                            col_label,
                            0,
                            i * ROW_HEIGHT,
                            TABLE_WIDTH,
                            ROW_HEIGHT,
                            style,
                            parent=cell_id,
                        )
                    )
            y_cursor += row_height + V_GAP

    edge_n = 0
    for _, metadata in sections:
        for table in metadata.tables.values():
            for column in table.columns:
                for fk in column.foreign_keys:
                    target_name = fk.column.table.name
                    if table.name not in table_cell_id or target_name not in table_cell_id:
                        continue
                    edge_n += 1
                    edges.append(
                        _edge(
                            f"edge_{edge_n}",
                            table_cell_id[table.name],
                            table_cell_id[target_name],
                            column.name,
                        )
                    )

    return _wrap("".join(cells) + "".join(edges))


def generate_state_diagram_xml(transitions: dict[str, list[str]], title: str) -> str:
    """Draws one box per state and one directed edge per allowed transition,
    straight from the same adjacency dict the routers validate against —
    see workflow_definitions.py. Nothing here is duplicated/hardcoded, so
    the diagram can never drift out of sync with what the backend actually
    enforces."""
    states = list(transitions.keys())
    for targets in transitions.values():
        for t in targets:
            if t not in states:
                states.append(t)

    cells = [
        _vertex(_sanitize_id("hdr", title), title, 40, 20, 400, 24, "text;fontStyle=1;fontSize=16;align=left;")
    ]
    state_cell_id = {}
    y_base = 70
    for i, state in enumerate(states):
        row, col = divmod(i, STATES_PER_ROW)
        x = 40 + col * (STATE_WIDTH + STATE_H_GAP)
        y = y_base + row * (STATE_HEIGHT + STATE_V_GAP)
        cell_id = _sanitize_id("state", state)
        state_cell_id[state] = cell_id
        cells.append(
            _vertex(
                cell_id,
                state,
                x,
                y,
                STATE_WIDTH,
                STATE_HEIGHT,
                "rounded=1;whiteSpace=wrap;html=1;fillColor=#dae8fc;strokeColor=#6c8ebf;",
            )
        )

    edges = []
    edge_n = 0
    for source, targets in transitions.items():
        for target in targets:
            edge_n += 1
            edges.append(_edge(f"edge_{edge_n}", state_cell_id[source], state_cell_id[target]))

    return _wrap("".join(cells) + "".join(edges))
