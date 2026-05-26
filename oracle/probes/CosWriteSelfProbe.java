import java.io.ByteArrayOutputStream;
import java.io.PrintStream;
import org.apache.pdfbox.cos.COSBoolean;
import org.apache.pdfbox.cos.COSFloat;
import org.apache.pdfbox.cos.COSInteger;
import org.apache.pdfbox.cos.COSName;
import org.apache.pdfbox.cos.COSNull;

/**
 * Live oracle probe: emit the exact bytes Apache PDFBox's per-type
 * {@code writePDF(OutputStream)} self-serialization methods produce for the
 * five COS scalar types that own a {@code writePDF} (COSFloat, COSInteger,
 * COSName, COSBoolean, COSNull). COSString / COSArray / COSDictionary /
 * COSStream have NO {@code writePDF} upstream -- they are serialized by
 * COSWriter -- so they are not part of the per-type self-write surface and are
 * covered by the COSWriter oracle elsewhere.
 *
 * Unlike WriteScalarProbe (one spec per process invocation), this probe runs a
 * fixed internal battery and prints one {@code label: <hex>} line per case so
 * the float battery (the wave-1415 fix area) round-trips in a single JVM start.
 *
 * Source is ASCII-only (non-ASCII / control name bytes use \\uXXXX escapes) so
 * the platform-default encoding javac assumes cannot mangle any literal.
 *
 * Usage: java -cp <jar>:<build> CosWriteSelfProbe
 */
public final class CosWriteSelfProbe {

    public static void main(String[] args) throws Exception {
        PrintStream out = new PrintStream(System.out, true, "UTF-8");

        // --- COSFloat.writePDF -- constructed from a double (no preserved text).
        // These exercise Float.toString shortest-digit + BigDecimal plain-string
        // expansion, the exact path the wave-1415 writer fix mirrors.
        double[] floats = {
            0.0, -0.0, 1.0, -1.0, 0.5, 2.5, 100.0, 3.14159,
            0.1, 0.2, 0.3, -0.000123, 123456789.0,
            0.3333333333333333, 1.0 / 3.0, 2.0 / 3.0,
            1e-4, 1e-3, 9.999999e-4, 1e7, 9999999.0, 1e8, 1.5e10,
            0.00001, 0.0001, 12345.678, -98765.4321,
            65504.0, 1.4e-45, 3.4028235e38, 1.0e-40,
            (double) Float.MIN_VALUE, (double) Float.MAX_VALUE
        };
        for (double d : floats) {
            ByteArrayOutputStream baos = new ByteArrayOutputStream();
            new COSFloat((float) d).writePDF(baos);
            // Label with the bit pattern so Python can reconstruct the identical
            // float32 unambiguously (decimal text could re-parse differently).
            out.print("float " + Float.floatToIntBits((float) d) + ": "
                    + toHex(baos.toByteArray()) + "\n");
        }

        // --- COSFloat.writePDF -- constructed from a STRING (preserved original
        // form round-trips verbatim when faithful).
        String[] floatStrings = {
            "0.1", "-0.000123", "123456789.0", "1.0", "0.0", "-0.0",
            "3.14", "00.10", "0.50", "1e3", ".5", "100",
        };
        for (String s : floatStrings) {
            ByteArrayOutputStream baos = new ByteArrayOutputStream();
            new COSFloat(s).writePDF(baos);
            out.print("floats " + s + ": " + toHex(baos.toByteArray()) + "\n");
        }

        // --- COSInteger.writePDF.
        long[] ints = {0L, 1L, -1L, 42L, -42L, 2147483647L, -2147483648L,
                       9223372036854775807L, -9223372036854775808L};
        for (long n : ints) {
            ByteArrayOutputStream baos = new ByteArrayOutputStream();
            COSInteger.get(n).writePDF(baos);
            out.print("int " + n + ": " + toHex(baos.toByteArray()) + "\n");
        }

        // --- COSName.writePDF -- escaping of non-printable / delimiter bytes.
        // getName()/UTF-8 drives the escape table: A-Z a-z 0-9 + - _ @ * $ ; .
        // pass through; everything else becomes #XX (uppercase hex).
        String[] names = {
            "Type", "Pages",
            "A B",                 // space -> #20
            "A#B",                 // hash itself -> #23
            "Name(1)",             // parens -> #28 #29
            "Tab\u0009Here",       // U+0009 (tab) control -> #09
            "Slash/Sub",           // slash -> #2F
            "Pct%X",               // percent -> #25
            "Hi\u00e9",            // e-acute -> UTF-8 c3 a9 -> #C3#A9
            "Em\u2014dash",        // em dash -> UTF-8 e2 80 94 -> #E2#80#94
            "Plus+Minus-Under_At@Star*Dollar$Semi;Dot.",  // all pass-through
            "",                    // empty name -> just '/'
            "Para\u00b6",          // pilcrow -> UTF-8 c2 b6
            "d\u007fl",            // DEL control -> #7F
            "z\u0000end",          // embedded NUL -> #00
        };
        for (String nm : names) {
            ByteArrayOutputStream baos = new ByteArrayOutputStream();
            COSName.getPDFName(nm).writePDF(baos);
            out.print("name " + toHex(nm.getBytes("UTF-8")) + ": "
                    + toHex(baos.toByteArray()) + "\n");
        }

        // --- COSBoolean.writePDF.
        for (boolean b : new boolean[] {true, false}) {
            ByteArrayOutputStream baos = new ByteArrayOutputStream();
            COSBoolean.getBoolean(b).writePDF(baos);
            out.print("bool " + b + ": " + toHex(baos.toByteArray()) + "\n");
        }

        // --- COSNull.writePDF.
        {
            ByteArrayOutputStream baos = new ByteArrayOutputStream();
            COSNull.NULL.writePDF(baos);
            out.print("null: " + toHex(baos.toByteArray()) + "\n");
        }
    }

    private static String toHex(byte[] b) {
        StringBuilder sb = new StringBuilder();
        for (byte x : b) {
            sb.append(String.format("%02x", x & 0xff));
        }
        return sb.toString();
    }
}
