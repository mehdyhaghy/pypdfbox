import java.io.File;
import java.io.PrintStream;
import java.util.ArrayList;
import java.util.Arrays;
import java.util.List;
import org.apache.pdfbox.Loader;
import org.apache.pdfbox.cos.COSArray;
import org.apache.pdfbox.cos.COSBase;
import org.apache.pdfbox.cos.COSBoolean;
import org.apache.pdfbox.cos.COSDictionary;
import org.apache.pdfbox.cos.COSDocument;
import org.apache.pdfbox.cos.COSFloat;
import org.apache.pdfbox.cos.COSInteger;
import org.apache.pdfbox.cos.COSName;
import org.apache.pdfbox.cos.COSNull;
import org.apache.pdfbox.cos.COSObject;
import org.apache.pdfbox.cos.COSObjectKey;
import org.apache.pdfbox.cos.COSStream;
import org.apache.pdfbox.cos.COSString;
import org.apache.pdfbox.pdmodel.PDDocument;

/**
 * Differential fuzz probe for the Apache PDFBox 3.0.7 COS OBJECT parse core —
 * {@code org.apache.pdfbox.pdfparser.BaseParser.parseDirObject} and the COS
 * container parsers it dispatches to ({@code parseCOSArray} /
 * {@code parseCOSDictionary} / {@code parseCOSString} / {@code parseCOSName} /
 * {@code parseCOSNumber}) as they are actually reached from a real document
 * body parse ({@code COSParser.parseObjectDynamically}). Wave 1516, agent A.
 *
 * <p>Complements {@code CosLexFuzzProbe}, which only fuzzes the date entry
 * point ({@code COSDictionary.getDate} → {@code DateConverter}). It also
 * complements the content-stream token probes ({@code ParseEdgeTokenProbe},
 * {@code ParseLiteralNameProbe}, {@code CosNumberOverflowProbe}) which drive
 * {@code PDFStreamParser.parseNextToken} in OPERATOR mode — there {@code true},
 * {@code false}, {@code null}, {@code R}, {@code endobj} are content-stream
 * operators, NOT COS objects. This probe instead exercises the BODY object
 * parser where those keywords ARE first-class COS objects (booleans, null,
 * indirect-reference recovery) and where array / dictionary FRAMING leniency
 * (odd dict token count, missing {@code >>}, unbalanced parens, stray bytes)
 * is decided.
 *
 * <h2>Input (file-driven manifest, same pattern as ResourcesLookupFuzzProbe)</h2>
 * The pypdfbox sibling
 * ({@code tests/cos/oracle/test_cos_object_parse_fuzz_wave1516.py}) writes a
 * deterministic corpus into a tmp dir: for every case it emits
 * {@code <case>.pdf}, a minimal PDF whose object {@code 1 0 obj} body is the
 * RAW fuzzed bytes, plus a valid catalog (object 2) and pages tree so the
 * document loads. A {@code manifest.txt} (one case name per line, in order)
 * drives both sides over the identical files. Both sides read the exact same
 * bytes from disk.
 *
 * <h2>Output grammar (one UTF-8 LF-terminated line per case)</h2>
 * <pre>
 *   CASE &lt;name&gt; &lt;projection&gt;
 * </pre>
 * where {@code projection} is a recursive fingerprint of the resolved COSBase
 * of object {@code 1 0 R}:
 * <pre>
 *   null
 *   bool(true|false)
 *   int(&lt;decimal&gt;)
 *   real(&lt;float32-bits-hex&gt;)
 *   name(/&lt;decodedName&gt;)
 *   str(&lt;hex-of-raw-bytes&gt;)
 *   ref(&lt;objNum&gt;,&lt;gen&gt;)            indirect reference placeholder
 *   array[&lt;child&gt;,&lt;child&gt;,...]
 *   dict{/&lt;K&gt;-&gt;&lt;child&gt;,...}        keys sorted by name
 *   stream{/&lt;K&gt;-&gt;&lt;child&gt;,...}      a COSStream (dict view, sorted)
 *   ABSENT                            object 1 0 R not in the pool
 *   ERR:&lt;ExceptionSimpleName&gt;        resolving object 1 0 R threw
 *   LOAD:&lt;ExceptionSimpleName&gt;       Loader.loadPDF threw
 * </pre>
 * Floats are projected as their IEEE-754 float32 bit pattern so the comparison
 * is repr-independent. String bytes are raw {@code getBytes()} hex.
 */
public final class CosObjectParseFuzzProbe {

    static PrintStream out;

    static String exc(Throwable e) {
        return e.getClass().getSimpleName();
    }

    static String hex(byte[] data) {
        StringBuilder sb = new StringBuilder();
        for (byte b : data) {
            sb.append(Character.forDigit((b >> 4) & 0xF, 16));
            sb.append(Character.forDigit(b & 0xF, 16));
        }
        return sb.toString();
    }

    /** Recursive COS fingerprint. {@code raw} keeps indirect refs un-resolved. */
    static String tag(COSBase base) {
        if (base == null || base instanceof COSNull) {
            return "null";
        }
        if (base instanceof COSObject) {
            COSObject o = (COSObject) base;
            return "ref(" + o.getObjectNumber() + "," + o.getGenerationNumber() + ")";
        }
        if (base instanceof COSBoolean) {
            return "bool(" + (((COSBoolean) base).getValue() ? "true" : "false") + ")";
        }
        if (base instanceof COSInteger) {
            return "int(" + ((COSInteger) base).longValue() + ")";
        }
        if (base instanceof COSFloat) {
            return "real(" + Integer.toHexString(
                    Float.floatToIntBits(((COSFloat) base).floatValue())) + ")";
        }
        if (base instanceof COSName) {
            return "name(/" + ((COSName) base).getName() + ")";
        }
        if (base instanceof COSString) {
            return "str(" + hex(((COSString) base).getBytes()) + ")";
        }
        if (base instanceof COSArray) {
            COSArray a = (COSArray) base;
            StringBuilder sb = new StringBuilder("array[");
            for (int i = 0; i < a.size(); i++) {
                if (i > 0) {
                    sb.append(',');
                }
                // a.get(i) returns the RAW backing entry (an indirect ref stays
                // a COSObject placeholder), so the projection pins FRAMING, not
                // cross-object resolution.
                sb.append(tag(a.get(i)));
            }
            return sb.append(']').toString();
        }
        if (base instanceof COSStream) {
            return "stream" + dictBody((COSDictionary) base);
        }
        if (base instanceof COSDictionary) {
            return "dict" + dictBody((COSDictionary) base);
        }
        return "unknown(" + base.getClass().getSimpleName() + ")";
    }

    static String dictBody(COSDictionary d) {
        List<COSName> keys = new ArrayList<>(d.keySet());
        keys.sort((x, y) -> x.getName().compareTo(y.getName()));
        StringBuilder sb = new StringBuilder("{");
        boolean first = true;
        for (COSName k : keys) {
            if (!first) {
                sb.append(',');
            }
            first = false;
            // getItem keeps an indirect reference as a COSObject placeholder.
            sb.append('/').append(k.getName()).append("->").append(tag(d.getItem(k)));
        }
        return sb.append('}').toString();
    }

    static String project(File pdf) {
        PDDocument doc = null;
        try {
            doc = Loader.loadPDF(pdf);
            COSDocument cos = doc.getDocument();
            COSObject obj = cos.getObjectFromPool(new COSObjectKey(1, 0));
            if (obj == null) {
                return "ABSENT";
            }
            try {
                // getObject() forces the lazy parse of object 1 0 R's body —
                // exactly the parseDirObject path under test.
                COSBase resolved = obj.getObject();
                if (resolved == null) {
                    return "ABSENT";
                }
                return tag(resolved);
            } catch (Throwable e) {
                return "ERR:" + exc(e);
            }
        } catch (Throwable e) {
            return "LOAD:" + exc(e);
        } finally {
            if (doc != null) {
                try {
                    doc.close();
                } catch (Exception ignored) {
                    // best-effort close
                }
            }
        }
    }

    static void runCase(File dir, String name) {
        File pdf = new File(dir, name + ".pdf");
        out.println("CASE " + name + " " + project(pdf));
    }

    public static void main(String[] args) throws Exception {
        out = new PrintStream(System.out, true, "UTF-8");
        File dir = new File(args[0]);
        File manifest = new File(dir, "manifest.txt");
        String[] names =
                new String(java.nio.file.Files.readAllBytes(manifest.toPath()),
                                java.nio.charset.StandardCharsets.UTF_8)
                        .split("\n");
        Arrays.stream(names)
                .map(String::trim)
                .filter(s -> !s.isEmpty())
                .forEach(name -> runCase(dir, name));
    }
}
