import java.io.ByteArrayOutputStream;
import java.io.OutputStream;
import java.io.PrintStream;
import org.apache.pdfbox.cos.COSArray;
import org.apache.pdfbox.cos.COSBase;
import org.apache.pdfbox.cos.COSName;
import org.apache.pdfbox.cos.COSStream;
import org.apache.pdfbox.pdfwriter.COSWriter;

/**
 * Live oracle probe: emit the exact bytes Apache PDFBox's {@code COSWriter}
 * produces when serialising a {@code COSStream} object (PDF 32000-1 §7.3.8).
 *
 * This pins the stream-object WIRE FORMAT that {@code COSWriter.visitFromStream}
 * owns — the surface complementary to CosStreamLenProbe (which pins the
 * length/filter encode contract on {@code COSStream} alone, not the writer):
 *
 *   - dictionary framing first ({@code << ... >>}) via visitFromDictionary;
 *   - then literally {@code stream} followed by a CR-LF pair (NOT a bare LF);
 *   - then the raw (already filter-encoded) body bytes verbatim;
 *   - then a CR-LF pair, then {@code endstream}, then a single LF (writeEOL,
 *     which is conditional — it is skipped if the last byte was already EOL,
 *     but {@code endstream} is not an EOL so a LF is always emitted here);
 *   - {@code /Length} is written as a DIRECT integer inside the stream dict
 *     (COSStream stores it via setInt/setLong on itself), never an indirect
 *     reference; on the standalone visitor path it equals getLength();
 *   - no {@code /DL} (decoded-length) entry is emitted for a plain stream —
 *     /DL is an ObjStm-only artifact of the compressed writer.
 *
 * {@code COSWriter.visitFromStream} is public and the {@code COSWriter(OutputStream)}
 * constructor wires the standard-output framing layer to the ByteArrayOutputStream
 * we pass, so the stream-object bytes land there directly (no document, no header,
 * no xref). currentObjectKey stays null and willEncrypt false, so no encryption
 * pass runs — exactly the plaintext wire bytes we want to compare.
 *
 * Output: one {@code <label>: <hex>} line per case for the full byte image, plus
 * {@code <label>_length: <int>} (the /Length dict entry as written) and
 * {@code <label>_has_dl: <true|false>} lines.
 *
 * Usage: java -cp <jar>:<build> StreamWireFormatProbe
 */
public final class StreamWireFormatProbe {

    // Fixed, compressible payload — repeated text so FlateDecode shrinks it.
    private static final byte[] PAYLOAD = buildPayload();

    private static byte[] buildPayload() {
        StringBuilder sb = new StringBuilder();
        for (int i = 0; i < 40; i++) {
            sb.append("BT /F1 12 Tf 72 720 Td (Wire format) Tj ET\n");
        }
        return sb.toString().getBytes(java.nio.charset.StandardCharsets.ISO_8859_1);
    }

    public static void main(String[] args) throws Exception {
        PrintStream out = new PrintStream(System.out, true, "UTF-8");

        // --- Case 1: empty stream (no body). hasData() == false, so no body
        // bytes are written between the two CR-LF pairs.
        COSStream empty = new COSStream();
        emit(out, "empty", empty);

        // --- Case 2: verbatim (unfiltered) body. /Length == payload length,
        // no /Filter.
        COSStream raw = new COSStream();
        try (OutputStream os = raw.createOutputStream()) {
            os.write(PAYLOAD);
        }
        emit(out, "raw", raw);

        // --- Case 3: FlateDecode body. /Length == encoded (compressed) length,
        // /Filter /FlateDecode in the dict, raw body = compressed bytes.
        COSStream flate = new COSStream();
        try (OutputStream os = flate.createOutputStream(COSName.FLATE_DECODE)) {
            os.write(PAYLOAD);
        }
        emit(out, "flate", flate);

        // --- Case 4: two-filter chain ASCII85 + Flate. /Filter is an array.
        COSStream chain = new COSStream();
        COSArray filters = new COSArray();
        filters.add(COSName.ASCII85_DECODE);
        filters.add(COSName.FLATE_DECODE);
        try (OutputStream os = chain.createOutputStream(filters)) {
            os.write(PAYLOAD);
        }
        emit(out, "chain", chain);

        // --- Case 5: a single-byte body — exercises the body-bytes path with a
        // minimal, fully-predictable payload (no compression).
        COSStream onebyte = new COSStream();
        try (OutputStream os = onebyte.createOutputStream()) {
            os.write('X');
        }
        emit(out, "onebyte", onebyte);
    }

    private static void emit(PrintStream out, String label, COSStream stream)
            throws Exception {
        ByteArrayOutputStream baos = new ByteArrayOutputStream();
        COSWriter writer = new COSWriter(baos);
        writer.visitFromStream(stream);
        out.print(label + ": " + toHex(baos.toByteArray()) + "\n");
        // /Length as written into the dict (direct integer).
        out.print(label + "_length: " + stream.getLong(COSName.LENGTH) + "\n");
        // /DL presence — should always be false for a plain stream.
        COSBase dl = stream.getDictionaryObject(COSName.DL);
        out.print(label + "_has_dl: " + (dl != null) + "\n");
        stream.close();
    }

    private static String toHex(byte[] b) {
        StringBuilder sb = new StringBuilder();
        for (byte x : b) {
            sb.append(String.format("%02x", x & 0xff));
        }
        return sb.toString();
    }
}
