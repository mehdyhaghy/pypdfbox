import java.lang.reflect.Field;
import org.apache.pdfbox.cos.COSArray;
import org.apache.pdfbox.cos.COSBase;
import org.apache.pdfbox.cos.COSDictionary;
import org.apache.pdfbox.cos.COSFloat;
import org.apache.pdfbox.cos.COSInteger;
import org.apache.pdfbox.cos.COSName;
import org.apache.pdfbox.cos.COSNull;
import org.apache.pdfbox.cos.COSObject;
import org.apache.pdfbox.cos.COSStream;
import org.apache.pdfbox.pdmodel.DefaultResourceCache;
import org.apache.pdfbox.pdmodel.ResourceCache;
import org.apache.pdfbox.pdmodel.common.function.PDFunction;
import org.apache.pdfbox.pdmodel.graphics.form.PDFormXObject;
import org.apache.pdfbox.pdmodel.graphics.form.PDTransparencyGroup;
import org.apache.pdfbox.pdmodel.graphics.state.PDSoftMask;

/** Direct malformed-dictionary oracle for PDFBox 3.0.7 PDSoftMask. */
public final class SoftMaskDictionaryFuzzProbe {
    private static final COSName TAG = COSName.getPDFName("Tag");

    private static COSObject indirect(COSBase value) {
        return new COSObject(value);
    }

    private static COSArray array(int size) {
        COSArray value = new COSArray();
        for (int index = 0; index < size; index++) {
            value.add(new COSFloat(index + 0.25f));
        }
        return value;
    }

    private static COSDictionary function(int type) {
        COSDictionary value = new COSDictionary();
        value.setInt(COSName.FUNCTION_TYPE, type);
        return value;
    }

    private static COSStream form(String tag, boolean transparency) {
        COSStream stream = new COSStream();
        stream.setName(COSName.SUBTYPE, "Form");
        stream.setName(TAG, tag);
        stream.setItem(COSName.RESOURCES, new COSDictionary());
        if (transparency) {
            COSDictionary group = new COSDictionary();
            group.setName(COSName.S, "Transparency");
            stream.setItem(COSName.GROUP, group);
        }
        return stream;
    }

    private static COSStream subtypeStream(String subtype) {
        COSStream stream = new COSStream();
        if (subtype != null) {
            stream.setName(COSName.SUBTYPE, subtype);
        }
        return stream;
    }

    private static String createProjection(COSBase base, ResourceCache cache) {
        try {
            PDSoftMask mask = PDSoftMask.create(base, cache);
            if (mask == null) {
                return "null";
            }
            return mask.getCOSObject() == base ? "mask:same" : "mask:other";
        } catch (Exception exception) {
            return "ERR";
        }
    }

    private static void emitCreate(String name, COSBase base) {
        String plain = createProjection(base, null);
        String cached = createProjection(base, new DefaultResourceCache());
        System.out.println("CREATE " + name + " plain=" + plain + " cached=" + cached);
    }

    private static String subtype(PDSoftMask mask) {
        try {
            COSName value = mask.getSubType();
            return value == null ? "null" : value.getName();
        } catch (Exception exception) {
            return "ERR";
        }
    }

    private static String group(PDSoftMask mask) {
        try {
            PDTransparencyGroup value = mask.getGroup();
            if (value == null) {
                return "null";
            }
            String tag = value.getCOSObject().getNameAsString(TAG);
            return "group:" + (tag == null ? "none" : tag);
        } catch (Exception exception) {
            return "ERR";
        }
    }

    private static String backdrop(PDSoftMask mask) {
        try {
            COSArray value = mask.getBackdropColor();
            return value == null ? "null" : "array:" + value.size();
        } catch (Exception exception) {
            return "ERR";
        }
    }

    private static String transfer(PDSoftMask mask) {
        try {
            PDFunction value = mask.getTransferFunction();
            if (value == null) {
                return "null";
            }
            String name = value.getClass().getSimpleName();
            return name.startsWith("PDFunctionType")
                    ? name.substring("PDFunctionType".length()).toLowerCase()
                    : name;
        } catch (Exception exception) {
            return "ERR";
        }
    }

    private static String cache(PDSoftMask mask, ResourceCache expected) {
        try {
            PDTransparencyGroup value = mask.getGroup();
            if (value == null) {
                return "na";
            }
            Field field = PDFormXObject.class.getDeclaredField("cache");
            field.setAccessible(true);
            Object actual = field.get(value);
            if (actual == expected) {
                return expected == null ? "null" : "same";
            }
            return "other";
        } catch (Exception exception) {
            return "ERR";
        }
    }

    private static void emit(String name, COSDictionary dictionary) {
        emit(name, dictionary, null);
    }

    private static void emit(
            String name, COSDictionary dictionary, ResourceCache resourceCache) {
        PDSoftMask mask = new PDSoftMask(dictionary, resourceCache);
        System.out.println(
                "CASE " + name
                        + " s=" + subtype(mask)
                        + " g=" + group(mask)
                        + " bc=" + backdrop(mask)
                        + " tr=" + transfer(mask)
                        + " cache=" + cache(mask, resourceCache));
    }

    private static void emitEntry(String name, COSName key, COSBase value) {
        COSDictionary dictionary = new COSDictionary();
        dictionary.setItem(key, value);
        emit(name, dictionary);
    }

    private static void emitFactoryCases() {
        emitCreate("null", null);
        emitCreate("none", COSName.NONE);
        emitCreate("dict", new COSDictionary());
        emitCreate("stream", new COSStream());
        emitCreate("name", COSName.getPDFName("Bad"));
        emitCreate("integer", COSInteger.ONE);
        emitCreate("array", new COSArray());
        emitCreate("cos_null", COSNull.NULL);
        emitCreate("indirect_none", indirect(COSName.NONE));
        emitCreate("indirect_dict", indirect(new COSDictionary()));
        emitCreate("indirect_null", indirect(COSNull.NULL));
    }

    private static void emitSubtypeCases() {
        emit("empty", new COSDictionary());
        emitEntry("s_alpha", COSName.S, COSName.ALPHA);
        emitEntry("s_luminosity", COSName.S, COSName.LUMINOSITY);
        emitEntry("s_unknown", COSName.S, COSName.getPDFName("Unknown"));
        emitEntry("s_integer", COSName.S, COSInteger.ONE);
        emitEntry("s_null", COSName.S, COSNull.NULL);
        emitEntry("s_indirect", COSName.S, indirect(COSName.ALPHA));
        emitEntry("s_indirect_wrong", COSName.S, indirect(COSInteger.ONE));
        emitEntry("s_indirect_null", COSName.S, indirect(COSNull.NULL));
    }

    private static void emitGroupCases() {
        emitEntry("g_group", COSName.G, form("direct", true));
        emitEntry("g_form", COSName.G, form("plain", false));
        emitEntry("g_image", COSName.G, subtypeStream("Image"));
        emitEntry("g_ps", COSName.G, subtypeStream("PS"));
        emitEntry("g_bad_subtype", COSName.G, subtypeStream("Bad"));
        emitEntry("g_no_subtype", COSName.G, subtypeStream(null));
        emitEntry("g_dictionary", COSName.G, new COSDictionary());
        emitEntry("g_name", COSName.G, COSName.getPDFName("Bad"));
        emitEntry("g_null", COSName.G, COSNull.NULL);
        emitEntry("g_indirect_group", COSName.G, indirect(form("indirect", true)));
        emitEntry("g_indirect_form", COSName.G, indirect(form("indirect_plain", false)));
        emitEntry("g_indirect_wrong", COSName.G, indirect(new COSDictionary()));
        emitEntry("g_indirect_null", COSName.G, indirect(COSNull.NULL));

        DefaultResourceCache cache = new DefaultResourceCache();
        COSDictionary cached = new COSDictionary();
        cached.setItem(COSName.G, form("cached", true));
        emit("g_cache", cached, cache);
    }

    private static void emitBackdropCases() {
        emitEntry("bc_empty", COSName.BC, array(0));
        emitEntry("bc_three", COSName.BC, array(3));
        COSArray mixed = new COSArray();
        mixed.add(COSName.getPDFName("Bad"));
        mixed.add(COSNull.NULL);
        emitEntry("bc_mixed", COSName.BC, mixed);
        emitEntry("bc_name", COSName.BC, COSName.getPDFName("Bad"));
        emitEntry("bc_integer", COSName.BC, COSInteger.ONE);
        emitEntry("bc_null", COSName.BC, COSNull.NULL);
        emitEntry("bc_indirect", COSName.BC, indirect(array(2)));
        emitEntry("bc_indirect_wrong", COSName.BC, indirect(COSInteger.ONE));
        emitEntry("bc_indirect_null", COSName.BC, indirect(COSNull.NULL));
    }

    private static void emitTransferCases() {
        emitEntry("tr_identity", COSName.TR, COSName.IDENTITY);
        emitEntry("tr_type0", COSName.TR, function(0));
        emitEntry("tr_type2", COSName.TR, function(2));
        emitEntry("tr_type3", COSName.TR, function(3));
        emitEntry("tr_type4", COSName.TR, function(4));
        emitEntry("tr_no_type", COSName.TR, new COSDictionary());
        emitEntry("tr_unknown_type", COSName.TR, function(9));
        emitEntry("tr_name", COSName.TR, COSName.getPDFName("Bad"));
        emitEntry("tr_integer", COSName.TR, COSInteger.ONE);
        emitEntry("tr_array", COSName.TR, new COSArray());
        emitEntry("tr_null", COSName.TR, COSNull.NULL);
        emitEntry("tr_indirect_identity", COSName.TR, indirect(COSName.IDENTITY));
        emitEntry("tr_indirect_type2", COSName.TR, indirect(function(2)));
        emitEntry("tr_indirect_wrong", COSName.TR, indirect(COSInteger.ONE));
        emitEntry("tr_indirect_null", COSName.TR, indirect(COSNull.NULL));
    }

    private static void emitMutationCases() {
        COSDictionary subtypeDictionary = new COSDictionary();
        subtypeDictionary.setItem(COSName.S, COSName.ALPHA);
        PDSoftMask subtypeMask = new PDSoftMask(subtypeDictionary);
        String subtypeFirst = subtype(subtypeMask);
        subtypeDictionary.setItem(COSName.S, COSName.LUMINOSITY);
        System.out.println(
                "MUTATE s_cached first=" + subtypeFirst + " second=" + subtype(subtypeMask));

        COSDictionary subtypeRetryDictionary = new COSDictionary();
        subtypeRetryDictionary.setItem(COSName.S, COSInteger.ONE);
        PDSoftMask subtypeRetryMask = new PDSoftMask(subtypeRetryDictionary);
        String subtypeRetryFirst = subtype(subtypeRetryMask);
        subtypeRetryDictionary.setItem(COSName.S, COSName.ALPHA);
        System.out.println(
                "MUTATE s_retry first=" + subtypeRetryFirst
                        + " second=" + subtype(subtypeRetryMask));

        COSDictionary groupDictionary = new COSDictionary();
        groupDictionary.setItem(COSName.G, form("first", true));
        PDSoftMask groupMask = new PDSoftMask(groupDictionary);
        String groupFirst = group(groupMask);
        groupDictionary.setItem(COSName.G, form("second", true));
        System.out.println(
                "MUTATE g_cached first=" + groupFirst + " second=" + group(groupMask));

        COSDictionary groupRetryDictionary = new COSDictionary();
        groupRetryDictionary.setItem(COSName.G, form("plain_first", false));
        PDSoftMask groupRetryMask = new PDSoftMask(groupRetryDictionary);
        String groupRetryFirst = group(groupRetryMask);
        groupRetryDictionary.setItem(COSName.G, form("fixed", true));
        System.out.println(
                "MUTATE g_retry first=" + groupRetryFirst
                        + " second=" + group(groupRetryMask));

        COSDictionary backdropDictionary = new COSDictionary();
        backdropDictionary.setItem(COSName.BC, array(1));
        PDSoftMask backdropMask = new PDSoftMask(backdropDictionary);
        String backdropFirst = backdrop(backdropMask);
        backdropDictionary.setItem(COSName.BC, array(3));
        System.out.println(
                "MUTATE bc_cached first=" + backdropFirst
                        + " second=" + backdrop(backdropMask));

        COSDictionary backdropRetryDictionary = new COSDictionary();
        backdropRetryDictionary.setItem(COSName.BC, COSInteger.ONE);
        PDSoftMask backdropRetryMask = new PDSoftMask(backdropRetryDictionary);
        String backdropRetryFirst = backdrop(backdropRetryMask);
        backdropRetryDictionary.setItem(COSName.BC, array(2));
        System.out.println(
                "MUTATE bc_retry first=" + backdropRetryFirst
                        + " second=" + backdrop(backdropRetryMask));

        COSDictionary transferDictionary = new COSDictionary();
        transferDictionary.setItem(COSName.TR, function(2));
        PDSoftMask transferMask = new PDSoftMask(transferDictionary);
        String transferFirst = transfer(transferMask);
        transferDictionary.setItem(COSName.TR, function(3));
        System.out.println(
                "MUTATE tr_cached first=" + transferFirst
                        + " second=" + transfer(transferMask));

        COSDictionary transferRetryDictionary = new COSDictionary();
        transferRetryDictionary.setItem(COSName.TR, function(9));
        PDSoftMask transferRetryMask = new PDSoftMask(transferRetryDictionary);
        String transferRetryFirst = transfer(transferRetryMask);
        transferRetryDictionary.setItem(COSName.TR, function(2));
        System.out.println(
                "MUTATE tr_retry first=" + transferRetryFirst
                        + " second=" + transfer(transferRetryMask));
    }

    public static void main(String[] args) {
        emitFactoryCases();
        emitSubtypeCases();
        emitGroupCases();
        emitBackdropCases();
        emitTransferCases();
        emitMutationCases();
    }
}
