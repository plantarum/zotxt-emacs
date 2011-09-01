
var EXPORTED_SYMBOLS = ["instantiateCiteProc", "getItemId", "registerItemIds", "getCitationBlock", "getBibliographyData"];

var zotero = Components.classes["@zotero.org/Zotero;1"].getService().wrappedJSObject;

function getItemId (idStr) {
    if (!idStr.match(/^[0-9]+_/)) {
        idStr = "0_" + idStr;
	}
	var lkh = zotero.Items.parseLibraryKeyHash(idStr);
	var item = zotero.Items.getByLibraryAndKey(lkh.libraryID, lkh.key);
	return item.id;
};

/*
* Locale will be the Zotero export locale.
*/
function instantiateCiteProc (styleid) {
	// Suspenders and a belt.
	try {
		if (!styleid) {
			styleid = "chicago-author-date";
		}
		if (styleid.slice(0,7) !== 'http://') {
			styleid = 'http://www.zotero.org/styles/' + styleid;
		}
		zotero.debug("XXX does this exist?: " + styleid);
		var style = zotero.Styles.get(styleid);
		zotero.reStructuredCSL = style.csl;
		zotero.reStructuredCSL.setOutputFormat("html");
	} catch (e) {
		zotero.debug("XXX instantiateCiteProc oops: " + e);
	}
};


function registerItemIds (ids) {
	zotero.reStructuredCSL.updateItems(ids);
};

function getCitationBlock (citation) {
	try {
            zotero.debug(citation);
		var ret = zotero.reStructuredCSL.appendCitationCluster(citation, true);
	} catch (e) {
		zotero.debug("XXX  oops: "+e);
	}
	zotero.debug("XXX ret[0][1]: " + ret[0][1]);
	var retme = "" + ret[0][1];
	// This should be binary Unicode now
	retme = escape( retme );
	return retme
};

function escapeStringValues (o) {
    if (Object.prototype.toString.call(o) === '[object Array]') {
        return o.map(function (x) { return escapeStringValues(x); });
    } else if (typeof o === "string") {
        return escape(o);
    } else if (typeof o === "object") {
        var retval = new Object();
        for (var k in o) {
            retval[k] = escapeStringValues(o[k]);
        }
        return retval;
    } else {
        return o;
    }
};

function getBibliographyData (arg) {
	var ret;
	zotero.debug("XXX WTF?");
	try {
		zotero.debug("XXX WTF? part two");
		ret = zotero.reStructuredCSL.makeBibliography(arg);
		zotero.debug("XXX WTF? part three");
		if (ret) {
			zotero.debug("XXX WTF? part four");
                	ret = escapeStringValues(ret);
			ret = JSON.stringify(ret);
			zotero.debug("XXX WTF? part five");
		}
	} catch (e) {
		zotero.debug("XXX oops: "+e);
	}
	zotero.debug("XXX non-oops: "+ret);
	return ret;
};

function isInTextStyle() {
	var ret = false;
	if ('in-text' === zotero.reStructuredCSL.opt.xclass) {
		ret = true;
	}
	return ret;
};
