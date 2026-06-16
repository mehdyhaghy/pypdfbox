import java.io.PrintStream;
import org.apache.pdfbox.cos.COSBase;
import org.apache.pdfbox.cos.COSDictionary;
import org.apache.pdfbox.cos.COSFloat;
import org.apache.pdfbox.cos.COSInteger;
import org.apache.pdfbox.cos.COSName;
import org.apache.pdfbox.cos.COSNull;
import org.apache.pdfbox.cos.COSObject;
import org.apache.pdfbox.cos.COSStream;
import org.apache.pdfbox.cos.COSString;
import org.apache.pdfbox.pdmodel.graphics.color.PDOutputIntent;

/**
 * Differential malformed-dictionary probe for {@link PDOutputIntent} —
 * the {@code /OutputIntents} entry — Apache PDFBox 3.0.7 (wave 1540, agent C).
 *
 * <p>Two surfaces:
 * <ul>
 *   <li>{@code field &lt;field&gt; &lt;case&gt;}: build a fresh
 *       {@code /OutputIntent} {@link COSDictionary}, set a single entry to a
 *       (possibly malformed) value, and project one string accessor —
 *       {@code getOutputConditionIdentifier} / {@code getOutputCondition} /
 *       {@code getRegistryName} / {@code getInfo} (all {@code getString}, so
 *       only a {@code COSString} decodes; names/ints/null fall back to
 *       {@code null}). {@code null} stands in for a Java {@code null} return.
 *       The subtype field {@code subtype} reads {@code /S} via
 *       {@code getCOSObject().getNameAsString(COSName.S)} (PDFBox 3.0 has no
 *       {@code getSubtype()} accessor) — pypdfbox's {@code get_subtype()} uses
 *       {@code getName}, so the honest divergence (string-under-/S) is pinned
 *       on the Python side.</li>
 *   <li>{@code profile &lt;case&gt;}: vary {@code /DestOutputProfile} —
 *       absent / non-stream (dict, name, int, null) / empty stream / stream
 *       with bytes — and project {@code getDestOutputIntent() != null} plus the
 *       decoded byte length ({@code -1} when absent/non-stream).</li>
 * </ul>
 */
public final class OutputIntentFuzzProbe {

    static COSName name(String value) {
        return COSName.getPDFName(value);
    }

    static String nz(String s) {
        return s == null ? "null" : s;
    }

    // ---- string-field surface: malformed entry values ----

    static COSBase fieldValue(String caseName) {
        switch (caseName) {
            case "absent":
                return null;
            case "string":
                return new COSString("sRGB");
            case "empty_string":
                return new COSString("");
            case "name":
                return name("sRGB");
            case "int":
                return COSInteger.get(42);
            case "float":
                return new COSFloat(2.5f);
            case "null":
                return COSNull.NULL;
            case "dict":
                return new COSDictionary();
            case "ind_string":
                return new COSObject(new COSString("sRGB"));
            case "ind_name":
                return new COSObject(name("sRGB"));
            case "ind_null":
                return new COSObject(COSNull.NULL);
            default:
                throw new IllegalArgumentException(caseName);
        }
    }

    static COSName keyForField(String field) {
        switch (field) {
            case "condid":
                return COSName.getPDFName("OutputConditionIdentifier");
            case "condition":
                return COSName.getPDFName("OutputCondition");
            case "registry":
                return COSName.getPDFName("RegistryName");
            case "info":
                return COSName.getPDFName("Info");
            case "subtype":
                return COSName.S;
            default:
                throw new IllegalArgumentException(field);
        }
    }

    static String projectField(PDOutputIntent oi, String field) {
        switch (field) {
            case "condid":
                return nz(oi.getOutputConditionIdentifier());
            case "condition":
                return nz(oi.getOutputCondition());
            case "registry":
                return nz(oi.getRegistryName());
            case "info":
                return nz(oi.getInfo());
            case "subtype":
                // PDFBox 3.0 has no getSubtype(); read /S as a name-or-string.
                return nz(oi.getCOSObject().getNameAsString(COSName.S));
            default:
                throw new IllegalArgumentException(field);
        }
    }

    static void runField(String field, String caseName) {
        COSDictionary dict = new COSDictionary();
        dict.setItem(COSName.TYPE, COSName.getPDFName("OutputIntent"));
        COSBase value = fieldValue(caseName);
        if (value != null) {
            dict.setItem(keyForField(field), value);
        }
        PDOutputIntent oi = new PDOutputIntent(dict);
        String result;
        try {
            result = projectField(oi, field);
        } catch (Exception e) {
            result = "ERR:" + e.getClass().getSimpleName();
        }
        System.out.println("value=" + result);
    }

    // ---- /DestOutputProfile surface ----

    static COSStream streamWith(byte[] data) {
        COSStream stream = new COSStream();
        try {
            java.io.OutputStream out = stream.createOutputStream();
            out.write(data);
            out.close();
        } catch (java.io.IOException e) {
            throw new RuntimeException(e);
        }
        return stream;
    }

    static COSBase profileValue(String caseName) {
        switch (caseName) {
            case "absent":
                return null;
            case "empty_stream":
                return streamWith(new byte[0]);
            case "stream":
                return streamWith(new byte[] {1, 2, 3, 4, 5});
            case "dict":
                return new COSDictionary();
            case "name":
                return name("DestOutputProfile");
            case "int":
                return COSInteger.get(7);
            case "null":
                return COSNull.NULL;
            case "ind_stream":
                return new COSObject(streamWith(new byte[] {9, 8, 7}));
            default:
                throw new IllegalArgumentException(caseName);
        }
    }

    static void runProfile(String caseName) {
        COSDictionary dict = new COSDictionary();
        dict.setItem(COSName.TYPE, COSName.getPDFName("OutputIntent"));
        COSBase value = profileValue(caseName);
        if (value != null) {
            dict.setItem(COSName.getPDFName("DestOutputProfile"), value);
        }
        PDOutputIntent oi = new PDOutputIntent(dict);
        String present;
        String len;
        try {
            COSStream profile = oi.getDestOutputIntent();
            present = profile == null ? "null" : "stream";
            if (profile == null) {
                len = "-1";
            } else {
                java.io.ByteArrayOutputStream baos = new java.io.ByteArrayOutputStream();
                java.io.InputStream in = profile.createInputStream();
                byte[] buf = new byte[8192];
                int read;
                while ((read = in.read(buf)) != -1) {
                    baos.write(buf, 0, read);
                }
                in.close();
                len = Integer.toString(baos.size());
            }
        } catch (Exception e) {
            present = "ERR:" + e.getClass().getSimpleName();
            len = "-1";
        }
        System.out.println("present=" + present + " len=" + len);
    }

    public static void main(String[] args) {
        switch (args[0]) {
            case "field":
                runField(args[1], args[2]);
                break;
            case "profile":
                runProfile(args[1]);
                break;
            default:
                throw new IllegalArgumentException(args[0]);
        }
    }
}
