// Pure lookup shared by the standalone page and behavior tests.
function lookupWord(raw, dictionary) {
 const word=String(raw).trim().replace(/’/g,"'").replace(/^[“”"'.,;:!?()[\]{}]+|[“”"'.,;:!?()[\]{}]+$/g,'').toLowerCase();
 if(!/^[a-z]+(?:['-][a-z]+)*$/.test(word))return null;
 return {word,entry:Object.prototype.hasOwnProperty.call(dictionary,word)?dictionary[word]:null};
}
