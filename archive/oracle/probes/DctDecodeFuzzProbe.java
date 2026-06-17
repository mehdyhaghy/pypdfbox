import java.io.ByteArrayInputStream;
import java.io.ByteArrayOutputStream;
import java.io.File;
import java.io.PrintStream;
import java.nio.file.Files;
import java.security.MessageDigest;
import org.apache.pdfbox.cos.COSDictionary;
import org.apache.pdfbox.cos.COSInteger;
import org.apache.pdfbox.cos.COSName;
import org.apache.pdfbox.filter.Filter;
import org.apache.pdfbox.filter.FilterFactory;

/**
 * Live oracle probe for {@code /DCTDecode} (JPEG / DCT) DECODE under malformed
 * and forged JPEG input (wave 1528 differential DCT fuzz).
 *
 * A DCT-specific complement to the generic wave-1505 {@link FilterFuzzProbe}.
 * Where that probe drives every codec uniformly, this one exists to (a) make
 * the DCT decode contract explicit and (b) accept an optional /DecodeParms
 * {@code ColorTransform} entry (0 / 1) so the YCbCr / RGB / CMYK colour-
 * transform variants can be exercised the same way pypdfbox passes them.
 *
 * It reads raw (encoded, possibly corrupt) JPEG bytes from a file, runs them
 * through Apache PDFBox's {@code DCTFilter.decode}, and prints a stable
 * projection of the OUTCOME rather than the raw raster:
 *
 *   ok=true
 *   len=&lt;decoded raster byte count&gt;
 *   sha=&lt;first 8 hex chars of SHA-256 of the decoded bytes&gt;
 *
 * or the sole line
 *
 *   ok=false
 *
 * on any throw from {@code Filter.decode}. PDFBox's DCTFilter.decode actually
 * runs the JPEG through ImageIO and emits the decompressed interleaved raster
 * (8x8 RGB -&gt; 192 bytes, etc.), so {@code len} is the raster size, not the
 * JPEG size. Empty / header-only / truncated-scan / SOF-marker-corrupt input
 * all throw -&gt; {@code ok=false}.
 *
 * Usage:
 *   java -cp ... DctDecodeFuzzProbe jpeg.bin
 *   java -cp ... DctDecodeFuzzProbe jpeg.bin 1     # /DecodeParms ColorTransform=1
 *
 *   args[0] - path to a file holding the raw (encoded) JPEG bytes.
 *   args[1] - OPTIONAL integer /DecodeParms ColorTransform value (0 or 1).
 *             Omitted / empty -&gt; no /DecodeParms entry.
 *
 * The decoded raster is buffered fully (the fuzz corpus is tiny) so it can be
 * length-and-hashed deterministically. Throwable (not just Exception) is caught
 * so a pathological forged-dimension allocation that surfaces as an Error also
 * classifies cleanly as ok=false.
 */
public final class DctDecodeFuzzProbe {
    public static void main(String[] args) throws Exception {
        byte[] encoded = Files.readAllBytes(new File(args[0]).toPath());

        COSDictionary streamDict = new COSDictionary();
        streamDict.setItem(COSName.FILTER, COSName.DCT_DECODE);

        if (args.length > 1 && !args[1].isEmpty()) {
            COSDictionary decodeParms = new COSDictionary();
            decodeParms.setItem(
                    COSName.getPDFName("ColorTransform"),
                    COSInteger.get(Long.parseLong(args[1].trim())));
            streamDict.setItem(COSName.DECODE_PARMS, decodeParms);
        }

        PrintStream out = System.out;
        Filter filter;
        try {
            filter = FilterFactory.INSTANCE.getFilter(COSName.DCT_DECODE);
        } catch (Exception e) {
            out.print("ok=false\n");
            out.flush();
            return;
        }

        ByteArrayOutputStream decoded = new ByteArrayOutputStream();
        try {
            filter.decode(new ByteArrayInputStream(encoded), decoded, streamDict, 0);
        } catch (Throwable t) {
            out.print("ok=false\n");
            out.flush();
            return;
        }

        byte[] bytes = decoded.toByteArray();
        out.print("ok=true\n");
        out.print("len=" + bytes.length + "\n");
        out.print("sha=" + shaPrefix(bytes) + "\n");
        out.flush();
    }

    private static String shaPrefix(byte[] data) throws Exception {
        MessageDigest md = MessageDigest.getInstance("SHA-256");
        byte[] digest = md.digest(data);
        StringBuilder sb = new StringBuilder();
        for (int i = 0; i < 4; i++) {
            sb.append(String.format("%02x", digest[i]));
        }
        return sb.toString();
    }
}
