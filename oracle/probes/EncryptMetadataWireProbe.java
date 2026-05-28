import java.io.File;
import java.io.PrintStream;
import java.nio.file.Files;
import org.apache.pdfbox.Loader;
import org.apache.pdfbox.cos.COSBase;
import org.apache.pdfbox.cos.COSDictionary;
import org.apache.pdfbox.cos.COSName;
import org.apache.pdfbox.cos.COSObject;
import org.apache.pdfbox.pdmodel.PDDocument;
import org.apache.pdfbox.pdmodel.encryption.PDEncryption;

/**
 * Live oracle probe for AES-256 /EncryptMetadata WIRE-BYTES parity.
 *
 * Per PDF 32000-1 §7.6.4.4.1, when the /Encrypt dictionary carries
 * /EncryptMetadata false, the catalog's /Metadata XMP stream MUST be left
 * cleartext on the wire (external indexers / library tooling can read it
 * without the password). The existing CryptFilterProbe asserts the
 * DECODED metadata content; this probe asserts the *on-disk raw bytes*
 * — proving the stream block between ``stream\\n`` and ``\\nendstream``
 * really is unenciphered.
 *
 * Sub-command:
 *
 *   inspect <encrypted.pdf> <password>
 *       Print, one per line:
 *         ENCRYPT_METADATA:<true|false|absent>  -- /Encrypt /EncryptMetadata
 *                                                 boolean ("absent" when the
 *                                                 entry is missing → spec
 *                                                 default true)
 *         METADATA_OBJ:<objNum genNum|->        -- catalog /Metadata object
 *                                                 key, or "-" if missing
 *         METADATA_RAW_LEN:<n|->                -- length of the on-disk
 *                                                 stream body (between
 *                                                 ``stream`` and ``endstream``,
 *                                                 stripping the spec
 *                                                 EOL pair surrounding each
 *                                                 token), or "-"
 *         METADATA_RAW_HEX:<hex|->              -- first 32 bytes of the
 *                                                 on-disk stream body as
 *                                                 lower-case hex, or "-"
 *         METADATA_LOOKS_XML:<true|false|->     -- heuristic: does the on-
 *                                                 disk prefix start with
 *                                                 "<?xpacket" or "<?xml" or
 *                                                 "<" (cleartext XMP) — or
 *                                                 is it cipher-looking
 *
 * Strategy: load the doc with PDFBox so we can find which indirect object the
 * catalog /Metadata entry resolves to (getObjectNumber / getGenerationNumber
 * on the COSObject reference, no decryption of the body required). Then read
 * the file bytes ourselves and locate the matching ``<N> <G> obj`` /
 * ``endobj`` pair, isolating the ``stream\\n ... \\nendstream`` payload.
 * This bypasses PDFBox's automatic stream-decrypt pass — exactly what we
 * need to SEE whether the writer enciphered the metadata or not.
 *
 * A wrong password makes Loader throw InvalidPasswordException (non-zero
 * exit), surfaced via the harness's CalledProcessError contract.
 */
public final class EncryptMetadataWireProbe {

    public static void main(String[] args) throws Exception {
        PrintStream out = new PrintStream(System.out, true, "UTF-8");
        String cmd = args[0];
        if ("inspect".equals(cmd)) {
            inspect(out, args[1], args[2]);
            return;
        }
        throw new IllegalArgumentException("unknown command: " + cmd);
    }

    private static void inspect(PrintStream out, String path, String password)
            throws Exception {
        File file = new File(path);
        byte[] fileBytes = Files.readAllBytes(file.toPath());

        long objNum = -1;
        long genNum = -1;
        String encryptMeta = "absent";

        try (PDDocument doc = Loader.loadPDF(file, password)) {
            PDEncryption enc = doc.getEncryption();
            if (enc != null) {
                COSDictionary encDict = enc.getCOSObject();
                COSBase emBase = encDict.getDictionaryObject(
                        COSName.ENCRYPT_META_DATA);
                if (emBase == null) {
                    encryptMeta = "absent";
                } else {
                    encryptMeta = Boolean.toString(enc.isEncryptMetaData());
                }
            }

            COSDictionary catalog = doc.getDocumentCatalog().getCOSObject();
            COSBase metaBase = catalog.getItem(COSName.METADATA);
            if (metaBase instanceof COSObject) {
                COSObject obj = (COSObject) metaBase;
                objNum = obj.getObjectNumber();
                genNum = obj.getGenerationNumber();
            }
        }

        out.print("ENCRYPT_METADATA:");
        out.print(encryptMeta);
        out.print("\n");

        if (objNum < 0) {
            out.print("METADATA_OBJ:-\n");
            out.print("METADATA_RAW_LEN:-\n");
            out.print("METADATA_RAW_HEX:-\n");
            out.print("METADATA_LOOKS_XML:-\n");
            return;
        }

        out.print("METADATA_OBJ:");
        out.print(objNum);
        out.print(" ");
        out.print(genNum);
        out.print("\n");

        byte[] body = extractRawStreamBody(fileBytes, objNum, genNum);
        if (body == null) {
            out.print("METADATA_RAW_LEN:-\n");
            out.print("METADATA_RAW_HEX:-\n");
            out.print("METADATA_LOOKS_XML:-\n");
            return;
        }

        out.print("METADATA_RAW_LEN:");
        out.print(body.length);
        out.print("\n");

        int prefixLen = Math.min(32, body.length);
        out.print("METADATA_RAW_HEX:");
        out.print(toHex(body, prefixLen));
        out.print("\n");

        out.print("METADATA_LOOKS_XML:");
        out.print(Boolean.toString(looksLikeXml(body)));
        out.print("\n");
    }

    /**
     * Locate ``<N> <G> obj ... stream\\n ... \\nendstream`` in raw file bytes.
     * Returns the on-disk stream body (the bytes between ``stream`` + EOL and
     * the EOL + ``endstream``), or null if the object isn't found / isn't a
     * stream. Honours PDF 32000-1 §7.3.8.1 EOL conventions: ``stream`` is
     * followed by CRLF or just LF; ``endstream`` is preceded by an EOL that
     * the writer added but which is NOT part of the stream data.
     */
    private static byte[] extractRawStreamBody(
            byte[] data, long objNum, long genNum) {
        String header = objNum + " " + genNum + " obj";
        byte[] needle = header.getBytes();
        int objStart = indexOf(data, needle, 0);
        if (objStart < 0) {
            return null;
        }
        int objEnd = indexOf(data, "endobj".getBytes(), objStart);
        if (objEnd < 0) {
            objEnd = data.length;
        }
        int streamTok = indexOf(data, "stream".getBytes(), objStart);
        if (streamTok < 0 || streamTok >= objEnd) {
            return null;
        }
        // Skip the ``stream`` keyword + its trailing EOL (CRLF or LF).
        int bodyStart = streamTok + "stream".length();
        if (bodyStart < data.length && data[bodyStart] == (byte) '\r') {
            bodyStart++;
        }
        if (bodyStart < data.length && data[bodyStart] == (byte) '\n') {
            bodyStart++;
        }
        int endStream = indexOf(data, "endstream".getBytes(), bodyStart);
        if (endStream < 0 || endStream > objEnd) {
            return null;
        }
        // Strip the EOL pair immediately before ``endstream`` (writer-added,
        // not part of the stream data per §7.3.8.1).
        int bodyEnd = endStream;
        if (bodyEnd > bodyStart && data[bodyEnd - 1] == (byte) '\n') {
            bodyEnd--;
        }
        if (bodyEnd > bodyStart && data[bodyEnd - 1] == (byte) '\r') {
            bodyEnd--;
        }
        if (bodyEnd <= bodyStart) {
            return new byte[0];
        }
        byte[] out = new byte[bodyEnd - bodyStart];
        System.arraycopy(data, bodyStart, out, 0, out.length);
        return out;
    }

    private static int indexOf(byte[] data, byte[] needle, int from) {
        if (needle.length == 0 || from < 0) {
            return -1;
        }
        outer:
        for (int i = from; i <= data.length - needle.length; i++) {
            for (int j = 0; j < needle.length; j++) {
                if (data[i + j] != needle[j]) {
                    continue outer;
                }
            }
            return i;
        }
        return -1;
    }

    private static boolean looksLikeXml(byte[] body) {
        if (body.length == 0) {
            return false;
        }
        byte first = body[0];
        // Cleartext XMP packets start with the BOM-less ``<?xpacket``,
        // ``<?xml`` declaration, or simply ``<`` opening an element. AES
        // ciphertext is uniformly random — the first byte being any of those
        // would be a 3/256 false-positive risk we accept (the 32-byte hex is
        // the authoritative signal; this flag is the convenience predicate).
        return first == (byte) '<';
    }

    private static String toHex(byte[] data, int len) {
        StringBuilder sb = new StringBuilder(len * 2);
        for (int i = 0; i < len; i++) {
            byte b = data[i];
            sb.append(Character.forDigit((b >> 4) & 0xF, 16));
            sb.append(Character.forDigit(b & 0xF, 16));
        }
        return sb.toString();
    }
}
