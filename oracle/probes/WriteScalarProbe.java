import java.io.ByteArrayOutputStream;
import java.io.PrintStream;
import org.apache.pdfbox.cos.COSBoolean;
import org.apache.pdfbox.cos.COSFloat;
import org.apache.pdfbox.cos.COSInteger;
import org.apache.pdfbox.cos.COSName;
import org.apache.pdfbox.cos.COSNull;
import org.apache.pdfbox.cos.COSString;
import org.apache.pdfbox.pdfwriter.COSWriter;

/**
 * Live oracle probe: emit the exact bytes Apache PDFBox writes for individual
 * COS scalar objects, using the same serialization paths COSWriter drives.
 *
 * Usage: java -cp <jar>:<build> WriteScalarProbe <spec> [<arg> ...]
 *
 * Specs (one per invocation), output is "<spec-echo>: <hex-of-written-bytes>":
 *   float   <text-or-double>   -> new COSFloat((float) double).writePDF(out)
 *   floats  <text>             -> new COSFloat(String).writePDF(out)  (round-trip form)
 *   int     <long>             -> COSInteger.get(long).writePDF(out)
 *   name    <utf8>             -> COSName.getPDFName(String).writePDF(out)
 *   nameb   <hexbytes>         -> COSName from raw bytes (rare), writePDF(out)
 *   strlit  <hexbytes>         -> COSWriter.writeString(new COSString(bytes), out)
 *   strhex  <hexbytes>         -> same, with setForceHexForm(true)
 *   bool    <true|false>       -> COSBoolean.getBoolean(b).writePDF(out)
 *   null                       -> COSNull.NULL.writePDF(out)
 *
 * Float values are passed as decimal text and parsed to a Java double so the
 * single-precision/formatString path is exercised exactly as a freshly
 * constructed COSFloat (no preserved original text).
 */
public final class WriteScalarProbe {
    public static void main(String[] args) throws Exception {
        PrintStream out = new PrintStream(System.out, true, "UTF-8");
        ByteArrayOutputStream baos = new ByteArrayOutputStream();
        String kind = args[0];
        switch (kind) {
            case "float": {
                double d = Double.parseDouble(args[1]);
                new COSFloat((float) d).writePDF(baos);
                break;
            }
            case "floats": {
                new COSFloat(args[1]).writePDF(baos);
                break;
            }
            case "int": {
                COSInteger.get(Long.parseLong(args[1])).writePDF(baos);
                break;
            }
            case "name": {
                COSName.getPDFName(args[1]).writePDF(baos);
                break;
            }
            case "nameb": {
                COSName.getPDFName(new String(fromHex(args[1]),
                        java.nio.charset.StandardCharsets.ISO_8859_1)).writePDF(baos);
                break;
            }
            case "strlit": {
                COSString s = new COSString(fromHex(args[1]));
                COSWriter.writeString(s, baos);
                break;
            }
            case "strhex": {
                COSString s = new COSString(fromHex(args[1]));
                s.setForceHexForm(true);
                COSWriter.writeString(s, baos);
                break;
            }
            case "bool": {
                COSBoolean.getBoolean(Boolean.parseBoolean(args[1])).writePDF(baos);
                break;
            }
            case "null": {
                COSNull.NULL.writePDF(baos);
                break;
            }
            default:
                throw new IllegalArgumentException("unknown spec: " + kind);
        }
        StringBuilder echo = new StringBuilder();
        for (String a : args) {
            if (echo.length() > 0) {
                echo.append(' ');
            }
            echo.append(a);
        }
        out.print(echo.toString());
        out.print(": ");
        out.print(toHex(baos.toByteArray()));
    }

    private static byte[] fromHex(String hex) {
        int n = hex.length() / 2;
        byte[] b = new byte[n];
        for (int i = 0; i < n; i++) {
            b[i] = (byte) Integer.parseInt(hex.substring(2 * i, 2 * i + 2), 16);
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
