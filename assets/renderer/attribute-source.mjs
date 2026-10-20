export function byteIndex(text,column){let bytes=1,index=0;for(const char of text){if(bytes>=column)break;bytes+=new TextEncoder().encode(char).length;index+=char.length;}return index;}

export function columnIntervals(text,line,ranges){
 return ranges.filter(r=>r.startColumn!==undefined&&line>=r.startLine&&line<=r.endLine).map(r=>[
  line===r.startLine?byteIndex(text,r.startColumn):0,
  line===r.endLine?byteIndex(text,r.endColumn):text.length
 ]).sort((a,b)=>a[0]-b[0]);
}

export function isAttributeLine(source,line){
 return Boolean(source.attributeLines&&line>=source.attributeLines.startLine&&line<=source.attributeLines.endLine);
}
