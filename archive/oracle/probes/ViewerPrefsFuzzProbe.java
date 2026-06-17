import java.lang.reflect.Method;
import org.apache.pdfbox.cos.COSArray;
import org.apache.pdfbox.cos.COSBase;
import org.apache.pdfbox.cos.COSBoolean;
import org.apache.pdfbox.cos.COSDictionary;
import org.apache.pdfbox.cos.COSFloat;
import org.apache.pdfbox.cos.COSInteger;
import org.apache.pdfbox.cos.COSName;
import org.apache.pdfbox.cos.COSNull;
import org.apache.pdfbox.cos.COSNumber;
import org.apache.pdfbox.cos.COSObject;
import org.apache.pdfbox.cos.COSString;
import org.apache.pdfbox.pdmodel.interactive.viewerpreferences.PDViewerPreferences;

/**
 * Differential malformed-dictionary fuzz probe for PDViewerPreferences
 * (wave 1540, agent B).
 *
 * Sibling of the wave-1521 {@code ViewerPreferencesFuzzProbe}; this probe
 * widens the corpus to drive EVERY upstream-exposed getter
 * (getHideToolbar..getPrintScaling) plus a per-field projection of the
 * enrichment surface (/NumCopies, /PrintPageRange, /Enforce,
 * /PickTrayByPDFSize) that PDFBox 3.0.7 has no getter for — those are read
 * straight off the raw /ViewerPreferences COS dictionary so the Python
 * sibling can pin its enrichment accessors against the spec-correct raw
 * value PDFBox would surface.
 *
 * Each subcommand prints ONE canonical line. Output grammar mirrors the
 * Python sibling (test_viewer_prefs_fuzz_wave1540.py) byte-for-byte.
 *
 *   bool <case>      -> ht=<b> hm=<b> hw=<b> fw=<b> cw=<b> dd=<b> pt=<b>
 *   name <case>      -> nfs=<s> dir=<s> va=<s> vc=<s> pa=<s> pc=<s> dup=<s|NULL> ps=<s>
 *   num  <case>      -> api=<present|unsupported> raw=<...>
 *   range <case>     -> api=<present|unsupported> raw=<...>
 *   enforce <case>   -> api=<present|unsupported> raw=<...>
 *
 * Booleans render as "true"/"false"; an absent name renders "NULL".
 */
public final class ViewerPrefsFuzzProbe {

    private static final String[] BOOLEAN_KEYS = {
        "HideToolbar", "HideMenubar", "HideWindowUI", "FitWindow",
        "CenterWindow", "DisplayDocTitle", "PickTrayByPDFSize"
    };

    private static final String[] NAME_KEYS = {
        "NonFullScreenPageMode", "Direction", "ViewArea", "ViewClip",
        "PrintArea", "PrintClip", "Duplex", "PrintScaling"
    };

    private static COSName name(String value) {
        return COSName.getPDFName(value);
    }

    private static COSArray array(COSBase... values) {
        COSArray result = new COSArray();
        for (COSBase value : values) {
            result.add(value);
        }
        return result;
    }

    private static String nz(String v) {
        return v == null ? "NULL" : v;
    }

    private static String b(boolean v) {
        return v ? "true" : "false";
    }

    /** Canonical structural digest of one raw COS value (mirrors Python _raw). */
    private static String raw(COSBase value) {
        if (value == null) {
            return "null";
        }
        if (value instanceof COSBoolean) {
            return "bool:" + ((COSBoolean) value).getValue();
        }
        if (value instanceof COSName) {
            return "name:" + ((COSName) value).getName();
        }
        if (value instanceof COSString) {
            return "string:" + ((COSString) value).getString();
        }
        if (value instanceof COSInteger) {
            return "int:" + ((COSInteger) value).longValue();
        }
        if (value instanceof COSFloat) {
            return "float:" + ((COSFloat) value).floatValue();
        }
        if (value instanceof COSArray) {
            return "array:" + ((COSArray) value).size();
        }
        if (value instanceof COSDictionary) {
            return "dict";
        }
        return value.getClass().getSimpleName();
    }

    private static boolean hasMethod(String methodName) {
        for (Method method : PDViewerPreferences.class.getMethods()) {
            if (method.getName().equals(methodName)) {
                return true;
            }
        }
        return false;
    }

    // ---------------------------------------------------------------- booleans

    private static COSBase booleanValue(String caseName) {
        switch (caseName) {
            case "true":     return COSBoolean.TRUE;
            case "false":    return COSBoolean.FALSE;
            case "null":     return COSNull.NULL;
            case "int":      return COSInteger.ONE;
            case "int_zero": return COSInteger.ZERO;
            case "name":     return name("true");
            case "string":   return new COSString("true");
            case "float":    return new COSFloat(1.0f);
            case "ind_true": return new COSObject(COSBoolean.TRUE);
            case "ind_null": return new COSObject(COSNull.NULL);
            default:         throw new IllegalArgumentException(caseName);
        }
    }

    private static void runBooleans(String caseName) {
        COSDictionary d = new COSDictionary();
        if (!"absent".equals(caseName)) {
            COSBase value = booleanValue(caseName);
            for (String key : BOOLEAN_KEYS) {
                d.setItem(name(key), value);
            }
        }
        PDViewerPreferences p = new PDViewerPreferences(d);
        System.out.println("ht=" + b(p.hideToolbar())
                + " hm=" + b(p.hideMenubar())
                + " hw=" + b(p.hideWindowUI())
                + " fw=" + b(p.fitWindow())
                + " cw=" + b(p.centerWindow())
                + " dd=" + b(p.displayDocTitle())
                + " pt=" + b(p.getCOSObject()
                        .getBoolean(COSName.getPDFName("PickTrayByPDFSize"), false)));
    }

    // ------------------------------------------------------------------- names

    private static COSBase nameValue(String caseName, String validValue) {
        switch (caseName) {
            case "valid":      return name(validValue);
            case "bogus":      return name("Bogus");
            case "string":     return new COSString("Text");
            case "empty":      return new COSString("");
            case "wrong_int":  return COSInteger.ONE;
            case "wrong_bool": return COSBoolean.TRUE;
            case "null":       return COSNull.NULL;
            case "ind_valid":  return new COSObject(name(validValue));
            case "ind_string": return new COSObject(new COSString("Text"));
            case "ind_null":   return new COSObject(COSNull.NULL);
            default:           throw new IllegalArgumentException(caseName);
        }
    }

    private static void runNames(String caseName) {
        String[] valid = {
            "UseOutlines", "R2L", "MediaBox", "BleedBox",
            "TrimBox", "ArtBox", "Simplex", "None"
        };
        COSDictionary d = new COSDictionary();
        if (!"absent".equals(caseName)) {
            for (int i = 0; i < NAME_KEYS.length; i++) {
                d.setItem(name(NAME_KEYS[i]), nameValue(caseName, valid[i]));
            }
        }
        PDViewerPreferences p = new PDViewerPreferences(d);
        System.out.println("nfs=" + nz(p.getNonFullScreenPageMode())
                + " dir=" + nz(p.getReadingDirection())
                + " va=" + nz(p.getViewArea())
                + " vc=" + nz(p.getViewClip())
                + " pa=" + nz(p.getPrintArea())
                + " pc=" + nz(p.getPrintClip())
                + " dup=" + nz(p.getDuplex())
                + " ps=" + nz(p.getPrintScaling()));
    }

    // ------------------------------------------------------ /NumCopies (enrich)

    private static COSBase numValue(String caseName) {
        switch (caseName) {
            case "one":      return COSInteger.ONE;
            case "three":    return COSInteger.get(3);
            case "zero":     return COSInteger.ZERO;
            case "negative": return COSInteger.get(-5);
            case "huge":     return COSInteger.get(2147483648L);
            case "float":    return new COSFloat(2.0f);
            case "name":     return name("Three");
            case "string":   return new COSString("3");
            case "null":     return COSNull.NULL;
            case "ind_zero": return new COSObject(COSInteger.ZERO);
            default:         throw new IllegalArgumentException(caseName);
        }
    }

    private static void runNum(String caseName) {
        COSDictionary d = new COSDictionary();
        if (!"absent".equals(caseName)) {
            d.setItem(name("NumCopies"), numValue(caseName));
        }
        // PDFBox 3.0.7 has no getNumCopies — project the raw value and the
        // spec-correct int (Table 150 default 1) read off the raw dict.
        COSBase v = d.getDictionaryObject(name("NumCopies"));
        String specInt;
        if (v instanceof COSNumber) {
            int n = ((COSNumber) v).intValue();
            specInt = Integer.toString(n >= 1 ? n : 1);
        } else {
            specInt = "1";
        }
        String support = hasMethod("getNumCopies") ? "present" : "unsupported";
        System.out.println("api=" + support + " raw=" + raw(v) + " spec=" + specInt);
    }

    // --------------------------------------------------- /PrintPageRange (enrich)

    private static COSBase rangeValue(String caseName) {
        switch (caseName) {
            case "pair":       return array(COSInteger.ONE, COSInteger.get(3));
            case "two_pairs":  return array(COSInteger.ONE, COSInteger.get(3),
                                            COSInteger.get(5), COSInteger.get(9));
            case "odd":        return array(COSInteger.ONE, COSInteger.get(3),
                                            COSInteger.get(5));
            case "nonint":     return array(COSInteger.ONE, name("Two"));
            case "out_order":  return array(COSInteger.get(9), COSInteger.ONE);
            case "negative":   return array(COSInteger.get(-1), COSInteger.get(3));
            case "empty":      return new COSArray();
            case "wrong":      return new COSDictionary();
            case "null":       return COSNull.NULL;
            default:           throw new IllegalArgumentException(caseName);
        }
    }

    private static void runRange(String caseName) {
        COSDictionary d = new COSDictionary();
        if (!"absent".equals(caseName)) {
            d.setItem(name("PrintPageRange"), rangeValue(caseName));
        }
        COSBase v = d.getDictionaryObject(name("PrintPageRange"));
        // Spec-correct pair decode (PDF 32000-2 §12.4.4): even-length int
        // pairs; odd / non-int -> ignored (empty).
        String pairs = "";
        if (v instanceof COSArray) {
            COSArray a = (COSArray) v;
            int n = a.size();
            if (n % 2 == 0) {
                StringBuilder sb = new StringBuilder();
                boolean ok = true;
                for (int i = 0; i < n && ok; i++) {
                    if (!(a.getObject(i) instanceof COSInteger)) {
                        ok = false;
                    }
                }
                if (ok) {
                    for (int i = 0; i < n; i += 2) {
                        if (i > 0) {
                            sb.append(";");
                        }
                        sb.append(((COSInteger) a.getObject(i)).longValue())
                          .append(",")
                          .append(((COSInteger) a.getObject(i + 1)).longValue());
                    }
                }
                pairs = sb.toString();
            }
        }
        String support = hasMethod("getPrintPageRange") ? "present" : "unsupported";
        System.out.println("api=" + support + " raw=" + raw(v) + " pairs=[" + pairs + "]");
    }

    // -------------------------------------------------------- /Enforce (enrich)

    private static COSBase enforceValue(String caseName) {
        switch (caseName) {
            case "names":    return array(name("PrintScaling"), name("Duplex"));
            case "one_name": return array(name("PrintScaling"));
            case "mixed":    return array(name("Direction"), COSInteger.ONE,
                                          name("Duplex"));
            case "empty":    return new COSArray();
            case "wrong":    return name("PrintScaling");
            case "null":     return COSNull.NULL;
            default:         throw new IllegalArgumentException(caseName);
        }
    }

    private static void runEnforce(String caseName) {
        COSDictionary d = new COSDictionary();
        if (!"absent".equals(caseName)) {
            d.setItem(name("Enforce"), enforceValue(caseName));
        }
        COSBase v = d.getDictionaryObject(name("Enforce"));
        // Spec-correct name decode: non-name elements skipped.
        StringBuilder sb = new StringBuilder();
        if (v instanceof COSArray) {
            COSArray a = (COSArray) v;
            for (int i = 0; i < a.size(); i++) {
                if (a.getObject(i) instanceof COSName) {
                    if (sb.length() > 0) {
                        sb.append(",");
                    }
                    sb.append(((COSName) a.getObject(i)).getName());
                }
            }
        }
        String support = hasMethod("getEnforce") ? "present" : "unsupported";
        System.out.println("api=" + support + " raw=" + raw(v) + " names=[" + sb + "]");
    }

    public static void main(String[] args) {
        switch (args[0]) {
            case "bool":    runBooleans(args[1]); break;
            case "name":    runNames(args[1]); break;
            case "num":     runNum(args[1]); break;
            case "range":   runRange(args[1]); break;
            case "enforce": runEnforce(args[1]); break;
            default:        throw new IllegalArgumentException(args[0]);
        }
    }
}
