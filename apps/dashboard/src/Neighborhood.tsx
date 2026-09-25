import cytoscape, { type ElementDefinition, type StylesheetJson } from "cytoscape";
import { useEffect, useMemo, useRef } from "react";
import type { Investigation } from "./types";

const STYLE: StylesheetJson = [
  {
    selector: "node",
    style: {
      label: "data(label)",
      "text-wrap": "wrap",
      "text-max-width": "100px",
      "text-valign": "center",
      "text-halign": "center",
      "font-family": "Outfit, sans-serif",
      "font-size": 11,
      color: "#2c2824",
      "background-color": "#fffcf8",
      "border-width": 1,
      "border-color": "rgba(44, 40, 36, 0.16)",
      shape: "round-rectangle",
      width: 116,
      height: 46,
    },
  },
  {
    selector: "node.focus",
    style: {
      "border-width": 2,
      "border-color": "#a8843f",
    },
  },
  {
    selector: "node.phone",
    style: {
      "background-color": "#f3eee6",
    },
  },
  {
    selector: "node.quiet",
    style: {
      color: "#8a8178",
    },
  },
  {
    selector: "edge",
    style: {
      width: 1,
      "line-color": "rgba(44, 40, 36, 0.28)",
      "curve-style": "straight",
      "target-arrow-shape": "none",
    },
  },
];

function picture(cardId: string, txn: string, phone: boolean, others: string[], priors: string[], saved: string) {
  const nodes: ElementDefinition[] = [];
  const edges: ElementDefinition[] = [];
  nodes.push({
    data: { id: "card", label: cardId ? `This card\n${cardId}` : "This card" },
    classes: "focus",
    position: { x: 0, y: 0 },
  });
  if (txn) {
    nodes.push({ data: { id: "txn", label: `Purchase\n${txn}` }, position: { x: -200, y: 0 } });
    edges.push({ data: { id: "txn-card", source: "txn", target: "card" } });
  }
  if (phone) {
    nodes.push({ data: { id: "phone", label: "This phone" }, classes: "phone", position: { x: 200, y: 0 } });
    edges.push({ data: { id: "card-phone", source: "card", target: "phone" } });
    others.forEach((id, index) => {
      const y = (index - (others.length - 1) / 2) * 76;
      nodes.push({ data: { id: `other-${id}`, label: `Other card\n${id}` }, position: { x: 400, y } });
      edges.push({ data: { id: `phone-${id}`, source: "phone", target: `other-${id}` } });
    });
  }
  priors.forEach((id, index) => {
    const x = (index - (priors.length - 1) / 2) * 150;
    nodes.push({
      data: { id: `prior-${id}`, label: `Older case\n${id}` },
      classes: "quiet",
      position: { x, y: 140 },
    });
    edges.push({ data: { id: `card-${id}`, source: "card", target: `prior-${id}` } });
  });
  if (saved) {
    nodes.push({
      data: { id: "exam", label: `Saved\n${saved}` },
      classes: "quiet",
      position: { x: 0, y: -140 },
    });
    edges.push({ data: { id: "card-exam", source: "card", target: "exam" } });
  }
  return [...nodes, ...edges];
}

export function Neighborhood({ result, cardId }: { result: Investigation; cardId?: string }) {
  const host = useRef<HTMLDivElement>(null);
  const card = result.answer.case;
  const others = (result.demo.connected || card.connected_card_ids || [])
    .filter((id) => id && id !== cardId)
    .slice(0, 4);
  const priors = card.similar_prior_cases.slice(0, 3);
  const txn = result.demo.flagged?.txn_id || "";
  const phone = Boolean(result.demo.profile) || others.length > 0;
  const saved = card.written_to_graph && card.graph_case_id ? card.graph_case_id : "";
  const otherKey = others.join(",");
  const priorKey = priors.join(",");
  const elements = useMemo(
    () =>
      picture(
        cardId || "",
        txn,
        phone,
        otherKey ? otherKey.split(",") : [],
        priorKey ? priorKey.split(",") : [],
        saved,
      ),
    [cardId, txn, phone, saved, otherKey, priorKey],
  );
  const summary = useMemo(() => {
    const parts = [cardId ? `Card ${cardId}` : "This card"];
    if (txn) parts.push(`purchase ${txn}`);
    if (phone) parts.push("this phone");
    if (otherKey) parts.push(`other cards ${otherKey}`);
    if (priorKey) parts.push(`older cases ${priorKey}`);
    if (saved) parts.push(`saved as ${saved}`);
    return parts.join(". ");
  }, [cardId, txn, phone, otherKey, priorKey, saved]);

  useEffect(() => {
    const el = host.current;
    if (!el) return;
    const cy = cytoscape({
      container: el,
      elements,
      layout: { name: "preset" },
      minZoom: 0.2,
      maxZoom: 2,
      userZoomingEnabled: false,
      userPanningEnabled: false,
      boxSelectionEnabled: false,
      autoungrabify: true,
      style: STYLE,
    });
    const fit = () => {
      cy.resize();
      cy.fit(undefined, 18);
    };
    fit();
    const observer = new ResizeObserver(fit);
    observer.observe(el);
    return () => {
      observer.disconnect();
      cy.destroy();
    };
  }, [elements]);

  return <div ref={host} className="neighborhood" role="img" aria-label={summary} />;
}
