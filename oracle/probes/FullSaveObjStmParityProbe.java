import java.io.File;
import java.io.PrintStream;
import java.nio.file.Files;
import java.security.MessageDigest;
import java.util.ArrayList;
import java.util.List;
import java.util.regex.Matcher;
import java.util.regex.Pattern;
import java.util.zip.Inflater;
import org.apache.pdfbox.Loader;
import org.apache.pdfbox.pdfwriter.compress.CompressParameters;
import org.apache.pdfbox.pdmodel.PDDocument;

/**
 * Live oracle probe: perform a deterministic full COMPRESSED save
 * (``doc.save(out, new CompressParameters())``) over a source PDF, then report
 * the OBJECT-STREAM packing shape exactly as Apache PDFBox produces it:
 *
 *   objstm_count = number of /Type /ObjStm streams in the output
 *   index        = the xref stream's /Index array, comma-joined (sparse runs)
 *   w            = the xref stream's /W field array, comma-joined
 *   objstm<i>_n        = /N of the i-th ObjStm
 *   objstm<i>_first    = /First of the i-th ObjStm
 *   objstm<i>_nums     = the packed object numbers (index header), comma-joined
 *   objstm<i>_bodysha  = SHA-256 of the DECODED (inflated) ObjStm body
 *
 * The packed object-number lists, /Index runs and /W are deterministic
 * structure; the decoded-body SHA lets the Python side assert the
 * uncompressed payload matches byte-for-byte (the only legitimately divergent
 * residual is the deflate-compressed envelope: zlib vs java.util.zip.Deflater
 * on an identical uncompressed payload).
 *
 * Usage: java FullSaveObjStmParityProbe in.pdf out.pdf
 */
public final class FullSaveObjStmParityProbe {

    public static void main(String[] args) throws Exception {
        PrintStream out = new PrintStream(System.out, true, "UTF-8");
        File in = new File(args[0]);
        File outFile = new File(args[1]);

        try (PDDocument doc = Loader.loadPDF(in)) {
            doc.save(outFile, new CompressParameters());
        }

        byte[] full = Files.readAllBytes(outFile.toPath());
        String s = new String(full, "ISO-8859-1");

        // --- xref-stream /W + /Index ---
        int t = s.lastIndexOf("/Type /XRef");
        if (t < 0) {
            t = s.lastIndexOf("/Type/XRef");
        }
        int lineStart = s.lastIndexOf("\n", s.lastIndexOf(" obj", t)) + 1;
        String xdict = s.substring(lineStart, s.indexOf("stream", t));
        out.println("w=" + bracket(xdict, "/W"));
        out.println("index=" + bracket(xdict, "/Index"));

        // --- every /Type /ObjStm stream ---
        List<int[]> objstmFrames = new ArrayList<>();
        int from = 0;
        int count = 0;
        Pattern objHeader = Pattern.compile("(?m)^(\\d+) (\\d+) obj\\b");
        while (true) {
            int oi = s.indexOf("/Type /ObjStm", from);
            if (oi < 0) {
                oi = s.indexOf("/Type/ObjStm", from);
            }
            if (oi < 0) {
                break;
            }
            count++;
            // back up to the enclosing "<num> <gen> obj"
            int objStart = s.lastIndexOf(" obj", oi);
            int frameStart = s.lastIndexOf("\n", objStart) + 1;
            objstmFrames.add(new int[] {frameStart, oi});
            from = oi + 5;
        }
        out.println("objstm_count=" + count);

        for (int i = 0; i < objstmFrames.size(); i++) {
            int oi = objstmFrames.get(i)[1];
            int frameStart = objstmFrames.get(i)[0];
            String region = s.substring(frameStart);
            int n = intKey(region, "/N");
            int first = intKey(region, "/First");

            int streamKw = region.indexOf("stream");
            int dataStart = streamKw + "stream".length();
            if (region.charAt(dataStart) == '\r' && region.charAt(dataStart + 1) == '\n') {
                dataStart += 2;
            } else if (region.charAt(dataStart) == '\n' || region.charAt(dataStart) == '\r') {
                dataStart += 1;
            }
            int dataEnd = region.indexOf("endstream", dataStart);
            int rawEnd = dataEnd;
            byte[] regionBytes = region.getBytes("ISO-8859-1");
            while (rawEnd > dataStart
                    && (regionBytes[rawEnd - 1] == '\n' || regionBytes[rawEnd - 1] == '\r')) {
                rawEnd--;
            }
            byte[] raw = new byte[rawEnd - dataStart];
            System.arraycopy(regionBytes, dataStart, raw, 0, raw.length);
            byte[] dec = inflate(raw);

            // index header: <objnum> <offset> pairs, up to /First bytes
            String header = new String(dec, 0, first, "ISO-8859-1");
            Matcher m = Pattern.compile("(\\d+)\\s+\\d+").matcher(header);
            StringBuilder nums = new StringBuilder();
            while (m.find()) {
                if (nums.length() > 0) {
                    nums.append(",");
                }
                nums.append(m.group(1));
            }

            MessageDigest md = MessageDigest.getInstance("SHA-256");
            md.update(dec);
            StringBuilder sha = new StringBuilder();
            for (byte b : md.digest()) {
                sha.append(String.format("%02x", b & 0xff));
            }

            out.println("objstm" + i + "_n=" + n);
            out.println("objstm" + i + "_first=" + first);
            out.println("objstm" + i + "_nums=" + nums);
            out.println("objstm" + i + "_bodysha=" + sha);
            out.println("objstm" + i + "_bodylen=" + dec.length);
        }
    }

    private static int intKey(String region, String key) {
        Matcher m = Pattern.compile(Pattern.quote(key) + "\\s+(\\d+)").matcher(region);
        if (m.find()) {
            return Integer.parseInt(m.group(1));
        }
        return -1;
    }

    private static String bracket(String dict, String key) {
        int k = dict.indexOf(key);
        if (k < 0) {
            return "";
        }
        int open = dict.indexOf("[", k);
        int close = dict.indexOf("]", open);
        return dict.substring(open + 1, close).trim().replaceAll("\\s+", ",");
    }

    private static byte[] inflate(byte[] raw) throws Exception {
        Inflater inf = new Inflater();
        inf.setInput(raw);
        byte[] buf = new byte[4096];
        java.io.ByteArrayOutputStream bos = new java.io.ByteArrayOutputStream();
        while (!inf.finished()) {
            int got = inf.inflate(buf);
            if (got == 0 && (inf.needsInput() || inf.needsDictionary())) {
                break;
            }
            bos.write(buf, 0, got);
        }
        inf.end();
        return bos.toByteArray();
    }
}
