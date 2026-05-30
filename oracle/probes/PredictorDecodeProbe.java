import java.io.File;
import java.io.OutputStream;
import java.lang.reflect.Method;
import java.nio.file.Files;
import java.util.Arrays;

/**
 * Live oracle probe for Apache PDFBox's DECODE-side predictor primitive,
 * {@code Predictor.decodePredictorRow(int predictor, int colors,
 * int bitsPerComponent, int columns, byte[] actline, byte[] lastline)}.
 *
 * Unlike {@code PredictorProbe} (which exercises the *encode*-side
 * {@code PredictorOutputStream} via {@code wrapPredictor}), this probe calls the
 * exact static method pypdfbox's {@code Predictor.decode_predictor_row} mirrors,
 * isolated from the (de)compression stage. It reverses a stream of
 * already-predicted rows and writes the recovered raw bytes to stdout.
 *
 * For the PNG predictors (10..14) the input file is laid out as PDFBox lays out
 * a predicted /FlateDecode body: each row is prefixed by a 1-byte PNG filter
 * tag (0..4), and the effective per-row predictor handed to
 * {@code decodePredictorRow} is {@code 10 + tag}. For TIFF /Predictor 2 there is
 * no per-row tag byte; every row is {@code rowLength} bytes and the predictor is
 * a constant 2.
 *
 * Usage:
 *   java -cp ... PredictorDecodeProbe predicted.bin \
 *        Predictor=14,Columns=5,Colors=3,BitsPerComponent=8
 *
 *   args[0] - path to a file holding the PREDICTED (post-filter, pre-compress)
 *             bytes, row-major. PNG: each row prefixed by its filter-tag byte.
 *             TIFF P2: rows are bare (no tag).
 *   args[1] - comma-separated integer params; must include Predictor and the
 *             geometry (Columns/Colors/BitsPerComponent). Defaults mirror
 *             PDFBox: Colors=1, BitsPerComponent=8, Columns=1.
 *
 * {@code decodePredictorRow} is package-private, so we reach it via reflection.
 */
public final class PredictorDecodeProbe {
    public static void main(String[] args) throws Exception {
        byte[] data = Files.readAllBytes(new File(args[0]).toPath());

        int predictor = 1;
        int colors = 1;
        int bitsPerComponent = 8;
        int columns = 1;
        for (String pair : args[1].split(",")) {
            int eq = pair.indexOf('=');
            if (eq < 0) {
                continue;
            }
            String key = pair.substring(0, eq).trim();
            int value = Integer.parseInt(pair.substring(eq + 1).trim());
            switch (key) {
                case "Predictor":        predictor = value;        break;
                case "Colors":           colors = value;           break;
                case "BitsPerComponent": bitsPerComponent = value; break;
                case "Columns":          columns = value;          break;
                default: break;
            }
        }

        int rowLength = (columns * colors * bitsPerComponent + 7) / 8;

        Class<?> predictorClass = Class.forName("org.apache.pdfbox.filter.Predictor");
        Method decodeRow = predictorClass.getDeclaredMethod(
                "decodePredictorRow",
                int.class, int.class, int.class, int.class, byte[].class, byte[].class);
        decodeRow.setAccessible(true);

        OutputStream out = System.out;

        if (rowLength <= 0) {
            out.flush();
            return;
        }

        byte[] lastline = new byte[rowLength];

        if (predictor == 2) {
            // TIFF Predictor 2: no per-row tag byte; constant predictor 2.
            for (int pos = 0; pos + rowLength <= data.length; pos += rowLength) {
                byte[] actline = Arrays.copyOfRange(data, pos, pos + rowLength);
                decodeRow.invoke(null, 2, colors, bitsPerComponent, columns,
                        actline, lastline);
                out.write(actline);
                lastline = actline;
            }
        } else {
            // PNG predictors: each row prefixed by a 1-byte filter tag (0..4).
            int stride = rowLength + 1;
            for (int pos = 0; pos + stride <= data.length; pos += stride) {
                int tag = data[pos] & 0xFF;
                byte[] actline = Arrays.copyOfRange(data, pos + 1, pos + 1 + rowLength);
                decodeRow.invoke(null, 10 + tag, colors, bitsPerComponent, columns,
                        actline, lastline);
                out.write(actline);
                lastline = actline;
            }
        }
        out.flush();
    }
}
