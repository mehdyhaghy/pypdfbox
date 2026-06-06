import java.io.File;
import java.io.FileOutputStream;
import java.nio.file.Files;
import org.apache.pdfbox.Loader;
import org.apache.pdfbox.pdmodel.PDDocument;
import org.apache.pdfbox.pdmodel.PDDocumentInformation;

/**
 * Live oracle probe emitting the <b>appended tail</b> of an incremental save
 * as raw bytes (lowercase hex), so a parity test can compare it
 * byte-for-byte against pypdfbox's {@code save_incremental} output for the
 * exact same mutation.
 *
 * Usage:
 *   java IncrementalTailBytesProbe in.pdf out.pdf
 *
 * Mutation: set {@code /Info /Title} to {@code "DeltaTitle"} and flag the
 * /Info dict dirty, then {@code saveIncremental}. The appended tail is
 * everything after the original source length (the increment the writer
 * produced — new object bodies + new xref section/stream + trailer +
 * startxref + %%EOF).
 *
 * Output lines:
 *   source_len=<int>
 *   out_len=<int>
 *   tail_hex=<lowercase hex of out[source_len:]>
 *
 * The only non-deterministic bytes in the tail are the regenerated
 * {@code /ID[1]} octet string (ISO 32000-1 §14.4 requires the changing
 * identifier to be replaced); the parity harness masks the two /ID octet
 * strings on both sides before comparing.
 */
public final class IncrementalTailBytesProbe {

    private static String hex(byte[] b) {
        StringBuilder sb = new StringBuilder(b.length * 2);
        for (byte x : b) {
            sb.append(Character.forDigit((x >> 4) & 0xF, 16));
            sb.append(Character.forDigit(x & 0xF, 16));
        }
        return sb.toString();
    }

    public static void main(String[] args) throws Exception {
        File src = new File(args[0]);
        File out = new File(args[1]);
        byte[] srcBytes = Files.readAllBytes(src.toPath());
        int srcLen = srcBytes.length;

        try (PDDocument doc = Loader.loadPDF(src)) {
            PDDocumentInformation info = doc.getDocumentInformation();
            info.setTitle("DeltaTitle");
            info.getCOSObject().setNeedToBeUpdated(true);
            try (FileOutputStream os = new FileOutputStream(out)) {
                doc.saveIncremental(os);
            }
        }

        byte[] outBytes = Files.readAllBytes(out.toPath());
        byte[] tail = new byte[outBytes.length - srcLen];
        System.arraycopy(outBytes, srcLen, tail, 0, tail.length);

        StringBuilder sb = new StringBuilder();
        sb.append("source_len=").append(srcLen).append("\n");
        sb.append("out_len=").append(outBytes.length).append("\n");
        sb.append("tail_hex=").append(hex(tail)).append("\n");
        System.out.print(sb);
    }
}
