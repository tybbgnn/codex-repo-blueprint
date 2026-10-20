import assert from 'node:assert/strict';
import {byteIndex,columnIntervals,isAttributeLine} from './attribute-source.mjs';

const source={startLine:3537,endLine:3545,attributeLines:{startLine:3537,endLine:3537}};
const line='    #[tracing::instrument(level = "trace", skip_all, fields(item_count = items.len()))]';
const range={startLine:3537,startColumn:74,endLine:3537,endColumn:85};
assert(isAttributeLine(source,3537));
assert(!isAttributeLine(source,3538));
assert.deepEqual(columnIntervals(line,3537,[range]),[[73,84]]);
assert.equal(line.slice(...columnIntervals(line,3537,[range])[0]),'items.len()');
assert.equal(byteIndex('éitems',3),1);
console.log(JSON.stringify({passed:true,checks:5}));
