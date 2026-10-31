"""Génère le processus « Instruction d'un sinistre habitation » en BPMN 2.0.

Une seule description (couloirs, tâches, passerelle, flux, positions) produit :
- `instruction_sinistre.bpmn` : BPMN 2.0 XML avec diagramme, importable dans
  Bizagi Modeler, Enterprise Architect, Camunda Modeler ou bpmn.io ;
- `instruction_sinistre.svg` : la même figure, pour le rapport.

Usage : ``python docs/schemas/generer_bpmn.py``
"""
from pathlib import Path
from xml.sax.saxutils import escape

HERE = Path(__file__).resolve().parent
WIDTH, LANE_X, LABEL_W = 1700, 0, 40

LANES = [  # (id, nom, y, hauteur)
    ("lane_assure", "Assuré", 0, 170),
    ("lane_gestionnaire", "Gestionnaire de sinistres", 170, 200),
    ("lane_outil", "Outil d'aide à la décision", 370, 200),
]
# id: (type, nom, couloir, x, y, w, h)
NODES = {
    "debut": ("startEvent", "Sinistre survenu", "lane_assure", 90, 67, 36, 36),
    "declarer": ("task", "Déclarer le sinistre", "lane_assure", 160, 45, 130, 80),
    "ouvrir": ("task", "Ouvrir ou compléter le dossier", "lane_gestionnaire", 330, 230, 130, 80),
    "c12": ("serviceTask", "1-2. Police en vigueur, version applicable (SQL)", "lane_outil", 490, 430, 130, 80),
    "c3": ("serviceTask", "3. Garantie souscrite (classifieur + SQL)", "lane_outil", 650, 430, 130, 80),
    "c46": ("serviceTask", "4-6. Événement, exclusions, conditions (recherche + LLM vérifié)", "lane_outil", 810, 430, 130, 80),
    "c7": ("serviceTask", "7. Montant : plafond, franchise", "lane_outil", 970, 430, 130, 80),
    "verdict": ("businessRuleTask", "Déduire le verdict des contrôles", "lane_outil", 1130, 430, 130, 80),
    "gw": ("exclusiveGateway", "Verdict ?", "lane_outil", 1300, 445, 50, 50),
    "regler": ("userTask", "Valider et régler", "lane_gestionnaire", 1420, 180, 130, 55),
    "refus": ("userTask", "Notifier un refus motivé", "lane_gestionnaire", 1420, 245, 130, 55),
    "questions": ("userTask", "Demander les informations manquantes", "lane_gestionnaire", 1420, 310, 130, 55),
    "fournir": ("task", "Fournir les informations", "lane_assure", 1420, 45, 130, 80),
    "fin_regle": ("endEvent", "Dossier réglé", "lane_gestionnaire", 1600, 189, 36, 36),
    "fin_refus": ("endEvent", "Refus notifié", "lane_gestionnaire", 1600, 254, 36, 36),
}
# id: (source, cible, nom, points)
FLOWS = {
    "f1": ("debut", "declarer", "", [(126, 85), (160, 85)]),
    "f2": ("declarer", "ouvrir", "", [(225, 125), (225, 270), (330, 270)]),
    "f3": ("ouvrir", "c12", "", [(460, 270), (555, 270), (555, 430)]),
    "f4": ("c12", "c3", "", [(620, 470), (650, 470)]),
    "f5": ("c3", "c46", "", [(780, 470), (810, 470)]),
    "f6": ("c46", "c7", "", [(940, 470), (970, 470)]),
    "f7": ("c7", "verdict", "", [(1100, 470), (1130, 470)]),
    "f8": ("verdict", "gw", "", [(1260, 470), (1300, 470)]),
    "f9": ("gw", "regler", "Potentiellement couvert", [(1325, 445), (1325, 207), (1420, 207)]),
    "f10": ("gw", "refus", "Potentiellement exclu", [(1350, 470), (1375, 470), (1375, 272), (1420, 272)]),
    "f11": ("gw", "questions", "Indéterminé", [(1325, 495), (1325, 540), (1390, 540), (1390, 337), (1420, 337)]),
    "f12": ("regler", "fin_regle", "", [(1550, 207), (1600, 207)]),
    "f13": ("refus", "fin_refus", "", [(1550, 272), (1600, 272)]),
    "f14": ("questions", "fournir", "", [(1550, 337), (1575, 337), (1575, 85), (1550, 85)]),
    "f15": ("fournir", "ouvrir", "Informations reçues", [(1420, 85), (395, 85), (395, 230)]),
}


def bpmn_xml():
    out = ['<?xml version="1.0" encoding="UTF-8"?>',
           '<bpmn:definitions xmlns:bpmn="http://www.omg.org/spec/BPMN/20100524/MODEL" '
           'xmlns:bpmndi="http://www.omg.org/spec/BPMN/20100524/DI" '
           'xmlns:dc="http://www.omg.org/spec/DD/20100524/DC" '
           'xmlns:di="http://www.omg.org/spec/DD/20100524/DI" '
           'id="definitions" targetNamespace="https://github.com/metan40/claim-coverage-checker">',
           '  <bpmn:collaboration id="collaboration">',
           '    <bpmn:participant id="pool" name="Instruction d\'un sinistre habitation" processRef="process"/>',
           '  </bpmn:collaboration>',
           '  <bpmn:process id="process" isExecutable="false">',
           '    <bpmn:laneSet id="laneset">']
    for lane_id, name, *_ in LANES:
        out.append(f'      <bpmn:lane id="{lane_id}" name="{escape(name)}">')
        out += [f'        <bpmn:flowNodeRef>{n}</bpmn:flowNodeRef>' for n, v in NODES.items() if v[2] == lane_id]
        out.append('      </bpmn:lane>')
    out.append('    </bpmn:laneSet>')
    for node_id, (kind, name, *_rest) in NODES.items():
        incoming = [f for f, v in FLOWS.items() if v[1] == node_id]
        outgoing = [f for f, v in FLOWS.items() if v[0] == node_id]
        inner = "".join(f"<bpmn:incoming>{f}</bpmn:incoming>" for f in incoming)
        inner += "".join(f"<bpmn:outgoing>{f}</bpmn:outgoing>" for f in outgoing)
        out.append(f'    <bpmn:{kind} id="{node_id}" name="{escape(name)}">{inner}</bpmn:{kind}>')
    for flow_id, (src, dst, name, _) in FLOWS.items():
        label = f' name="{escape(name)}"' if name else ""
        out.append(f'    <bpmn:sequenceFlow id="{flow_id}" sourceRef="{src}" targetRef="{dst}"{label}/>')
    out += ['  </bpmn:process>', '  <bpmndi:BPMNDiagram id="diagram">',
            '    <bpmndi:BPMNPlane id="plane" bpmnElement="collaboration">',
            f'      <bpmndi:BPMNShape id="pool_di" bpmnElement="pool" isHorizontal="true">'
            f'<dc:Bounds x="{LANE_X}" y="0" width="{WIDTH}" height="570"/></bpmndi:BPMNShape>']
    for lane_id, _, y, h in LANES:
        out.append(f'      <bpmndi:BPMNShape id="{lane_id}_di" bpmnElement="{lane_id}" isHorizontal="true">'
                   f'<dc:Bounds x="{LANE_X + LABEL_W}" y="{y}" width="{WIDTH - LABEL_W}" height="{h}"/></bpmndi:BPMNShape>')
    for node_id, (kind, _, _, x, y, w, h) in NODES.items():
        marker = ' isMarkerVisible="true"' if kind == "exclusiveGateway" else ""
        out.append(f'      <bpmndi:BPMNShape id="{node_id}_di" bpmnElement="{node_id}"{marker}>'
                   f'<dc:Bounds x="{x}" y="{y}" width="{w}" height="{h}"/></bpmndi:BPMNShape>')
    for flow_id, (*_, points) in FLOWS.items():
        wp = "".join(f'<di:waypoint x="{px}" y="{py}"/>' for px, py in points)
        out.append(f'      <bpmndi:BPMNEdge id="{flow_id}_di" bpmnElement="{flow_id}">{wp}</bpmndi:BPMNEdge>')
    out += ['    </bpmndi:BPMNPlane>', '  </bpmndi:BPMNDiagram>', '</bpmn:definitions>']
    return "\n".join(out) + "\n"


def wrap(text, width=19):
    words, lines, line = text.split(), [], ""
    for word in words:
        if line and len(line) + 1 + len(word) > width:
            lines.append(line)
            line = word
        else:
            line = f"{line} {word}".strip()
    return lines + [line]


def svg():
    ink, accent, lane_fill = "#14213D", "#1F4E79", ["#F5F7FA", "#FFFFFF", "#EEF4FA"]
    s = [f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="-10 -40 {WIDTH + 20} 630" '
         f'font-family="Arial, Helvetica, sans-serif" font-size="11" fill="{ink}">',
         '<defs><marker id="arrow" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" '
         f'orient="auto"><path d="M0,0 L10,5 L0,10 z" fill="{ink}"/></marker></defs>',
         f'<text x="0" y="-18" font-size="15" font-weight="bold">Instruction d\'un sinistre habitation (BPMN 2.0)</text>']
    for (lane_id, name, y, h), fill in zip(LANES, lane_fill):
        s.append(f'<rect x="{LABEL_W}" y="{y}" width="{WIDTH - LABEL_W}" height="{h}" fill="{fill}" stroke="#9AA5B8"/>')
        s.append(f'<rect x="0" y="{y}" width="{LABEL_W}" height="{h}" fill="#DDE3EC" stroke="#9AA5B8"/>')
        cy = y + h / 2
        s.append(f'<text x="24" y="{cy}" transform="rotate(-90 24 {cy})" text-anchor="middle" font-weight="bold">{escape(name)}</text>')
    for flow_id, (_, _, name, points) in FLOWS.items():
        d = " ".join(f"{'M' if i == 0 else 'L'}{x},{y}" for i, (x, y) in enumerate(points))
        s.append(f'<path d="{d}" fill="none" stroke="{ink}" stroke-width="1.3" marker-end="url(#arrow)"/>')
        if name:
            (x1, y1), (x2, y2) = points[1], points[2] if len(points) > 2 else points[1]
            lx, ly = (points[-2][0] + 6, (points[-2][1] + points[-1][1]) / 2) if flow_id != "f15" else (700, 78)
            anchor = "start"
            if flow_id == "f9":
                lx, ly, anchor = 1318, 230, "end"
            if flow_id == "f10":
                lx, ly = 1382, 425
            if flow_id == "f11":
                lx, ly = 1335, 555
            s.append(f'<text x="{lx}" y="{ly}" font-size="10" font-style="italic" text-anchor="{anchor}">{escape(name)}</text>')
    for node_id, (kind, name, _, x, y, w, h) in NODES.items():
        if kind in ("startEvent", "endEvent"):
            r = w / 2
            sw = 1.5 if kind == "startEvent" else 3.5
            s.append(f'<circle cx="{x + r}" cy="{y + r}" r="{r}" fill="white" stroke="{ink}" stroke-width="{sw}"/>')
            for i, part in enumerate(wrap(name, 14)):
                s.append(f'<text x="{x + r}" y="{y + h + 14 + 12 * i}" text-anchor="middle" font-size="10">{escape(part)}</text>')
        elif kind == "exclusiveGateway":
            cx, cy = x + w / 2, y + h / 2
            s.append(f'<polygon points="{cx},{y} {x + w},{cy} {cx},{y + h} {x},{cy}" fill="white" stroke="{ink}" stroke-width="1.5"/>')
            s.append(f'<path d="M{cx - 8},{cy - 8} L{cx + 8},{cy + 8} M{cx + 8},{cy - 8} L{cx - 8},{cy + 8}" stroke="{ink}" stroke-width="3"/>')
            s.append(f'<text x="{cx - 2}" y="{y - 6}" text-anchor="end" font-size="10">{escape(name)}</text>')
        else:
            fill = "#E3ECF5" if kind in ("serviceTask", "businessRuleTask") else "white"
            s.append(f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="10" fill="{fill}" stroke="{accent}" stroke-width="1.5"/>')
            lines = wrap(name, 21)
            top = y + h / 2 - (len(lines) - 1) * 6.5 + 4
            for i, part in enumerate(lines):
                s.append(f'<text x="{x + w / 2}" y="{top + 13 * i}" text-anchor="middle">{escape(part)}</text>')
            icon = {"serviceTask": "⚙", "businessRuleTask": "▦", "userTask": "👤"}.get(kind)
            if icon and kind != "userTask":
                s.append(f'<text x="{x + 7}" y="{y + 14}" font-size="11">{icon}</text>')
    s.append(f'<text x="{LABEL_W}" y="602" font-size="10">Tâches bleues : automatiques (outil). Tâches blanches : humaines. '
             'Le verdict est déduit des contrôles ; la décision reste au gestionnaire.</text>')
    s.append("</svg>")
    return "\n".join(s) + "\n"


if __name__ == "__main__":
    (HERE / "instruction_sinistre.bpmn").write_text(bpmn_xml(), encoding="utf-8")
    (HERE / "instruction_sinistre.svg").write_text(svg(), encoding="utf-8")
    print("instruction_sinistre.bpmn et instruction_sinistre.svg écrits dans", HERE)
