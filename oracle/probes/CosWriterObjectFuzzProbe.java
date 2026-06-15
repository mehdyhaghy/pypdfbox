import java.io.ByteArrayOutputStream;
import java.io.PrintStream;
import org.apache.pdfbox.cos.COSArray;
import org.apache.pdfbox.cos.COSBase;
import org.apache.pdfbox.cos.COSBoolean;
import org.apache.pdfbox.cos.COSDictionary;
import org.apache.pdfbox.cos.COSFloat;
import org.apache.pdfbox.cos.COSInteger;
import org.apache.pdfbox.cos.COSName;
import org.apache.pdfbox.cos.COSNull;
import org.apache.pdfbox.cos.COSStream;
import org.apache.pdfbox.cos.COSString;
import org.apache.pdfbox.pdfwriter.COSWriter;

/**
 * Live oracle probe: the EXACT bytes Apache PDFBox's {@code COSWriter} emits for
 * INDIVIDUAL COS objects through its {@code visitFromXxx} dispatch — the
 * per-object serialization surface (number/boolean/null formatting, array and
 * dictionary container framing, the stream dict + body, nested structures).
 *
 * This complements the byte-level escaping probes ({@code CosStringWriteProbe},
 * {@code NameWriteEscapeProbe}) which pin the leaf string/name escape table; here
 * we drive the visitor entry points directly against a fresh {@code COSWriter}
 * wrapping a {@code ByteArrayOutputStream} and capture the framing bytes
 * (delimiters, EOLs, inter-element spacing, the every-10th-array-EOL rule,
 * trailing EOLs, ``stream``/``endstream`` keywords, the synthesized /Length).
 *
 * Each case prints {@code <tag> <id>: <outputHex>}. The python side rebuilds the
 * same object and asserts its own COSWriter visit method produces byte-identical
 * output. Source is ASCII-only.
 *
 * Usage: java -cp <pdfbox-app.jar>:<build> CosWriterObjectFuzzProbe
 */
public final class CosWriterObjectFuzzProbe {

    public static void main(String[] args) throws Exception {
        PrintStream out = new PrintStream(System.out, true, "UTF-8");

        // ---- booleans / null ----
        emitBool(out, "bool_true", true);
        emitBool(out, "bool_false", false);
        emitNull(out, "null");

        // ---- COSInteger ----
        long[] ints = {0L, 1L, -1L, 7L, -7L, 255L, 256L, -256L, 1000000L,
                2147483647L, -2147483648L, 9223372036854775807L,
                -9223372036854775808L};
        String[] intIds = {"i0", "i1", "ineg1", "i7", "ineg7", "i255", "i256",
                "ineg256", "i1m", "imax32", "imin32", "imax64", "imin64"};
        for (int i = 0; i < ints.length; i++) {
            emitInt(out, "int_" + intIds[i], ints[i]);
        }

        // ---- COSFloat (constructed from float, so no original-text shortcut) ----
        float[] floats = {0.0f, -0.0f, 1.0f, -1.0f, 0.5f, -0.5f, 0.1f, 100.0f,
                3.14159f, 1234.5f, 1e7f, 9999999.0f, 1e-3f, 1e-4f, 1e8f, 1e20f,
                1e-20f, 1e38f, 3.4028235e38f, 1.4e-45f, 123456.78f, -0.001f,
                42.0f, 1e-45f};
        String[] floatIds = {"f0", "fneg0", "f1", "fneg1", "fhalf", "fneghalf",
                "fpt1", "f100", "fpi", "f1234p5", "f1e7", "f9999999", "f1em3",
                "f1em4", "f1e8", "f1e20", "f1em20", "f1e38", "fmax", "fmin_sub",
                "f123456p78", "fneg0p001", "f42", "f1em45"};
        for (int i = 0; i < floats.length; i++) {
            emitFloat(out, "float_" + floatIds[i], floats[i]);
        }

        // ---- COSFloat constructed from a string (round-trip original text) ----
        String[] floatStrs = {"0.0", "1.5", "-2.500", "0.10", "00.50", "3.",
                ".5", "1e3", "1.0E-2", "--16.33", "0.-262", "-16.-33",
                "42", "100000000"};
        for (String fs : floatStrs) {
            emitFloatStr(out, "fstr", fs);
        }

        // ---- COSName (a few framing checks alongside the dedicated escape probe) ----
        emitName(out, "Type");
        emitName(out, "");
        emitName(out, "A B");
        emitName(out, "1Leading");

        // ---- COSString through visitFromString (literal vs hex selection) ----
        emitString(out, "str_empty", hex(""), false);
        emitString(out, "str_hello", hex("48656c6c6f"), false);
        emitString(out, "str_parens", hex("286129"), false);     // (a)
        emitString(out, "str_back", hex("5c"), false);            // backslash
        emitString(out, "str_high", hex("ff00"), false);          // -> hex
        emitString(out, "str_eol", hex("0d0a"), false);           // CR LF -> hex
        emitString(out, "str_forcehex", hex("4142"), true);       // AB forced hex

        // ---- COSArray framing ----
        emitArray(out, "arr_empty", new COSArray());
        emitArray(out, "arr_ints", arrayOf(ci(1), ci(2), ci(3)));
        emitArray(out, "arr_mixed", arrayOf(ci(0), COSBoolean.TRUE, COSNull.NULL,
                new COSFloat(1.5f), new COSString("x"), COSName.getPDFName("K")));
        // 10-element array: the 10th separator is an EOL, not a space.
        COSArray ten = new COSArray();
        for (int i = 0; i < 10; i++) {
            ten.add(ci(i));
        }
        emitArray(out, "arr_ten", ten);
        // 12-element array: EOL after item 10, then space, then last.
        COSArray twelve = new COSArray();
        for (int i = 0; i < 12; i++) {
            twelve.add(ci(i));
        }
        emitArray(out, "arr_twelve", twelve);
        // nested array
        COSArray nestedInner = arrayOf(ci(1), ci(2));
        emitArray(out, "arr_nested", arrayOf(ci(0), nestedInner, ci(3)));
        // array containing a direct dict
        COSDictionary dInArr = new COSDictionary();
        dInArr.setItem(COSName.getPDFName("A"), ci(1));
        emitArray(out, "arr_with_dict", arrayOf(dInArr, ci(9)));
        // array of a single null
        emitArray(out, "arr_null", arrayOf(COSNull.NULL));

        // ---- COSDictionary framing ----
        emitDict(out, "dict_empty", new COSDictionary());
        COSDictionary d1 = new COSDictionary();
        d1.setItem(COSName.getPDFName("Type"), COSName.getPDFName("Page"));
        emitDict(out, "dict_one", d1);
        COSDictionary d2 = new COSDictionary();
        d2.setItem(COSName.getPDFName("A"), ci(1));
        d2.setItem(COSName.getPDFName("B"), new COSFloat(2.5f));
        d2.setItem(COSName.getPDFName("C"), COSBoolean.FALSE);
        d2.setItem(COSName.getPDFName("D"), new COSString("v"));
        emitDict(out, "dict_multi", d2);
        // dict with a null value -> entry skipped
        COSDictionary dNull = new COSDictionary();
        dNull.setItem(COSName.getPDFName("Keep"), ci(1));
        dNull.setItem(COSName.getPDFName("Drop"), (COSBase) null);
        dNull.setItem(COSName.getPDFName("Also"), ci(2));
        emitDict(out, "dict_null_val", dNull);
        // nested dict
        COSDictionary inner = new COSDictionary();
        inner.setItem(COSName.getPDFName("X"), ci(1));
        COSDictionary outerD = new COSDictionary();
        outerD.setItem(COSName.getPDFName("Sub"), inner);
        emitDict(out, "dict_nested", outerD);
        // dict with array value
        COSDictionary dArr = new COSDictionary();
        dArr.setItem(COSName.getPDFName("L"), arrayOf(ci(1), ci(2)));
        emitDict(out, "dict_arr_val", dArr);
        // dict with a name needing escaping as the key
        COSDictionary dEsc = new COSDictionary();
        dEsc.setItem(COSName.getPDFName("A B"), ci(1));
        emitDict(out, "dict_esc_key", dEsc);

        // ---- COSStream ----
        emitStream(out, "stream_empty", new byte[0], null);
        emitStream(out, "stream_abc", "ABC".getBytes("US-ASCII"), null);
        // stream with extra dict entries
        COSDictionary extra = new COSDictionary();
        extra.setItem(COSName.getPDFName("Type"), COSName.getPDFName("X"));
        emitStream(out, "stream_with_dict", "hello world".getBytes("US-ASCII"),
                extra);
        // stream with binary body
        emitStream(out, "stream_binary", new byte[] {0, 1, (byte) 0xff, 10, 13},
                null);
    }

    // ---- emit helpers ----

    private static void emitBool(PrintStream out, String tag, boolean v)
            throws Exception {
        ByteArrayOutputStream baos = new ByteArrayOutputStream();
        COSWriter w = new COSWriter(baos);
        w.visitFromBoolean(v ? COSBoolean.TRUE : COSBoolean.FALSE);
        line(out, tag, "", baos);
    }

    private static void emitNull(PrintStream out, String tag) throws Exception {
        ByteArrayOutputStream baos = new ByteArrayOutputStream();
        COSWriter w = new COSWriter(baos);
        w.visitFromNull(COSNull.NULL);
        line(out, tag, "", baos);
    }

    private static void emitInt(PrintStream out, String tag, long v)
            throws Exception {
        ByteArrayOutputStream baos = new ByteArrayOutputStream();
        COSWriter w = new COSWriter(baos);
        w.visitFromInt(COSInteger.get(v));
        line(out, tag, Long.toString(v), baos);
    }

    private static void emitFloat(PrintStream out, String tag, float v)
            throws Exception {
        ByteArrayOutputStream baos = new ByteArrayOutputStream();
        COSWriter w = new COSWriter(baos);
        w.visitFromFloat(new COSFloat(v));
        line(out, tag, Float.toString(v), baos);
    }

    private static void emitFloatStr(PrintStream out, String tag, String s)
            throws Exception {
        ByteArrayOutputStream baos = new ByteArrayOutputStream();
        COSWriter w = new COSWriter(baos);
        w.visitFromFloat(new COSFloat(s));
        line(out, tag, s, baos);
    }

    private static void emitName(PrintStream out, String nm) throws Exception {
        ByteArrayOutputStream baos = new ByteArrayOutputStream();
        COSWriter w = new COSWriter(baos);
        w.visitFromName(COSName.getPDFName(nm));
        line(out, "name", toHex(nm.getBytes("UTF-8")), baos);
    }

    private static void emitString(PrintStream out, String tag, byte[] raw,
            boolean forceHex) throws Exception {
        ByteArrayOutputStream baos = new ByteArrayOutputStream();
        COSWriter w = new COSWriter(baos);
        COSString s = new COSString(raw);
        if (forceHex) {
            s.setForceHexForm(true);
        }
        w.visitFromString(s);
        line(out, tag, toHex(raw), baos);
    }

    private static void emitArray(PrintStream out, String tag, COSArray arr)
            throws Exception {
        ByteArrayOutputStream baos = new ByteArrayOutputStream();
        COSWriter w = new COSWriter(baos);
        w.visitFromArray(arr);
        line(out, tag, "", baos);
    }

    private static void emitDict(PrintStream out, String tag, COSDictionary d)
            throws Exception {
        ByteArrayOutputStream baos = new ByteArrayOutputStream();
        COSWriter w = new COSWriter(baos);
        w.visitFromDictionary(d);
        line(out, tag, "", baos);
    }

    private static void emitStream(PrintStream out, String tag, byte[] body,
            COSDictionary extraEntries) throws Exception {
        ByteArrayOutputStream baos = new ByteArrayOutputStream();
        COSWriter w = new COSWriter(baos);
        COSStream s = new COSStream();
        if (extraEntries != null) {
            s.addAll(extraEntries);
        }
        java.io.OutputStream cos = s.createRawOutputStream();
        cos.write(body);
        cos.close();
        w.visitFromStream(s);
        line(out, tag, "", baos);
    }

    // ---- builders ----

    private static COSInteger ci(long v) {
        return COSInteger.get(v);
    }

    private static COSArray arrayOf(COSBase... items) {
        COSArray a = new COSArray();
        for (COSBase b : items) {
            a.add(b);
        }
        return a;
    }

    // ---- output ----

    private static void line(PrintStream out, String tag, String id,
            ByteArrayOutputStream baos) {
        out.print(tag + " " + id + ": " + toHex(baos.toByteArray()) + "\n");
    }

    private static byte[] hex(String h) {
        int n = h.length() / 2;
        byte[] b = new byte[n];
        for (int i = 0; i < n; i++) {
            b[i] = (byte) Integer.parseInt(h.substring(2 * i, 2 * i + 2), 16);
        }
        return b;
    }

    private static String toHex(byte[] b) {
        StringBuilder sb = new StringBuilder();
        for (byte x : b) {
            sb.append(String.format("%02x", x & 0xff));
        }
        return sb.toString();
    }
}
