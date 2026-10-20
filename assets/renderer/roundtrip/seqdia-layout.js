// SeqDia contributors, MIT. Unmodified layout algorithm; TypeScript erased.
// Source commit 61d5e91fc87ee0b686695560e443c1232a191ec0. See vendor/seqdia/LICENSE-MIT.

function toSet(values) {
    if (!values) return undefined;
    return values instanceof Set ? values : new Set(values);
}
function normalizeActors(actors, parentActorId = null, depth = 0) {
    return actors.map((actor)=>({
            ...actor,
            parentActorId: parentActorId ?? actor.parentActorId ?? null,
            depth,
            children: normalizeActors(actor.children ?? [], actor.actorId, depth + 1)
        }));
}
function deriveExpandedActorIds(actors, expandedActorIds) {
    if (expandedActorIds) return expandedActorIds;
    const result = new Set();
    const walk = (nodes)=>{
        nodes.forEach((node)=>{
            const hasChildren = node.children.length > 0;
            if (hasChildren && (node.defaultExpanded ?? true)) {
                result.add(node.actorId);
            }
            walk(node.children);
        });
    };
    walk(actors);
    return result;
}
function computeVisibleActors(actors, expanded, headerRows, leafCounter, ancestorExpanded) {
    const visible = [];
    actors.forEach((node)=>{
        const hasChildren = node.children.length > 0;
        const isExpanded = ancestorExpanded && hasChildren && expanded.has(node.actorId);
        const childVisible = isExpanded ? computeVisibleActors(node.children, expanded, headerRows, leafCounter, true) : [];
        const leafStart = childVisible.length ? childVisible[0].leafStart : leafCounter.value++;
        const leafEnd = childVisible.length ? childVisible[childVisible.length - 1].leafEnd : leafStart;
        const leafSpan = leafEnd - leafStart + 1;
        const startBoundary = leafStart;
        const endBoundary = leafEnd + 1;
        const alignment = node.alignment ?? "center";
        const anchor = alignment === "left" ? startBoundary : alignment === "right" ? endBoundary : (startBoundary + endBoundary) / 2;
        const visibleNode = {
            actorId: node.actorId,
            label: node.label,
            depth: node.depth,
            parentActorId: node.parentActorId ?? null,
            children: childVisible,
            hasChildren,
            expanded: isExpanded,
            alignment,
            leafStart,
            leafEnd,
            leafSpan,
            anchor,
            isLeaf: childVisible.length === 0,
            className: node.className,
            regionClassName: node.regionClassName
        };
        headerRows[visibleNode.depth] = headerRows[visibleNode.depth] ?? [];
        headerRows[visibleNode.depth].push(visibleNode);
        visible.push(visibleNode, ...childVisible);
    });
    return visible;
}
function buildActorAncestryMap(actors, visibleActorMap, ancestorMap = new Map(), visibleAncestor = null) {
    actors.forEach((actor)=>{
        const isVisible = Boolean(visibleActorMap[actor.actorId]);
        const currentAncestor = isVisible ? actor.actorId : visibleAncestor;
        if (currentAncestor) {
            ancestorMap.set(actor.actorId, currentAncestor);
        }
        if (actor.children.length > 0) {
            buildActorAncestryMap(actor.children, visibleActorMap, ancestorMap, currentAncestor);
        }
    });
    return ancestorMap;
}
function resolveMessagesToVisibleActors(messages, visibleActorMap, ancestorMap) {
    return messages.map((message)=>{
        const resolvedFrom = ancestorMap.get(message.fromActorId);
        const resolvedTo = ancestorMap.get(message.toActorId);
        if (!resolvedFrom || !resolvedTo) {
            return null;
        }
        if (resolvedFrom === resolvedTo) {
            const isIntentionalSelfMessage = message.fromActorId === message.toActorId;
            if (!isIntentionalSelfMessage) {
                return null;
            }
        }
        return {
            ...message,
            fromActorId: resolvedFrom,
            toActorId: resolvedTo
        };
    }).filter((msg)=>msg !== null);
}
export function computeLayout(model, options = {}) {
    const headerRowHeight = options.headerRowHeight ?? 56;
    const rowHeight = options.messageRowHeight ?? 76;
    const rowPadding = options.messageRowPadding ?? 18;
    let previousTo = null;
    model.messages.forEach((message, idx)=>{
        if (previousTo !== null && message.fromActorId !== previousTo) {
            throw new Error(`Message sequence must be linear: message "${message.messageId}" starts at "${message.fromActorId}" but previous ended at "${previousTo}" (index ${idx})`);
        }
        previousTo = message.toActorId;
    });
    const normalizedActors = normalizeActors(model.actors);
    const expandedActors = deriveExpandedActorIds(normalizedActors, toSet(options.expandedActorIds));
    const headerRows = [];
    const leafCounter = {
        value: 0
    };
    const visibleActors = computeVisibleActors(normalizedActors, expandedActors, headerRows, leafCounter, true);
    const leafCount = Math.max(leafCounter.value, 1);
    const visibleActorMap = visibleActors.reduce((acc, actor)=>{
        acc[actor.actorId] = actor;
        return acc;
    }, {});
    const anchors = visibleActors.reduce((acc, actor)=>{
        acc[actor.actorId] = actor.anchor;
        return acc;
    }, {});
    const spans = visibleActors.reduce((acc, actor)=>{
        acc[actor.actorId] = {
            start: actor.leafStart,
            end: actor.leafEnd + 1
        };
        return acc;
    }, {});
    const ancestorMap = buildActorAncestryMap(normalizedActors, visibleActorMap);
    const visibleMessages = resolveMessagesToVisibleActors(model.messages, visibleActorMap, ancestorMap);
    const annotatedMessages = visibleMessages.map((message, idx)=>({
            message,
            order: idx,
            hint: message.rowIndex ?? idx
        }));
    annotatedMessages.sort((a, b)=>{
        if (a.hint === b.hint) return a.order - b.order;
        return a.hint - b.hint;
    });
    const messages = annotatedMessages.map((item, denseIndex)=>({
            message: item.message,
            rowIndex: denseIndex,
            y: rowPadding + denseIndex * rowHeight
        }));
    const messageAreaHeight = messages.length > 0 ? rowPadding * 2 + messages.length * rowHeight : rowPadding * 2 + rowHeight;
    const maxDepth = headerRows.length ? headerRows.length - 1 : 0;
    const headerHeight = (maxDepth + 1) * headerRowHeight;
    const totalHeight = headerHeight + messageAreaHeight;
    return {
        headerRows,
        visibleActors,
        visibleActorMap,
        leafCount,
        anchors,
        spans,
        messages,
        headerHeight,
        messageAreaHeight,
        totalHeight,
        rowHeight,
        headerRowHeight
    };
}
