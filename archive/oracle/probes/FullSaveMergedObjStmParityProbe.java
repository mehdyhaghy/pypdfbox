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
import org.apache.pdfbox.multipdf.PDFMergerUtility;
import org.apache.pdfbox.pdfwriter.compress.CompressParameters;
import org.apache.pdfbox.pdmodel.PDDocument;

/**
 * Live oracle probe: MERGE two source PDFs with {@link PDFMergerUtility} into an
 * intermediate file, then re-load that merged file and perform a deterministic
 * full COMPRESSED save ({@code doc.save(out, new CompressParameters())}), then
 * report the object-stream packing shape exactly as Apache PDFBox produces it —
 * identical key set to {@code FullSaveObjStmParityProbe}.
 *
 * The intermediate-then-recompress sequence mirrors the pypdfbox side exactly
 * (pypdfbox merges to a file with the legacy merger, then re-loads and
 * compress-saves through COSWriter), so the comparison isolates the COMPRESSED
 * SAVE traversal/packing of a deep-graph merged document — the wave-1506 concern.
 *
 * Usage: java FullSaveMergedObjStmParityProbe a.pdf b.pdf merged.pdf out.pdf
 */
public final class FullSaveMergedObjStmParityProbe {

    public static void main(String[] args) throws Exception {
        PrintStream out = new PrintStream(System.out, true, "UTF-8");
        File a = new File(args[0]);
        File b = new File(args[1]);
        File merged = new File(args[2]);
        File outFile = new File(args[3]);

        PDFMergerUtility merger = new PDFMergerUtility();
        merger.setDestinationFileName(merged.getAbsolutePath());
        merger.addSource(a);
        merger.addSource(b);
        merger.mergeDocuments(org.apache.pdfbox.io.IOUtils.createMemoryOnlyStreamCache());

        try (PDDocument doc = Loader.loadPDF(merged)) {
            doc.save(outFile, new CompressParameters());
        }

        byte[] full = Files.readAllBytes(outFile.toPath());
        String s = new String(full, "ISO-8859-1");

        int t = s.lastIndexOf("/Type /XRef");
        if (t < 0) {
            t = s.lastIndexOf("/Type/XRef");
        }
        int lineStart = s.lastIndexOf("\n", s.lastIndexOf(" obj", t)) + 1;
        String xdict = s.substring(lineStart, s.indexOf("stream", t));
        out.println("w=" + bracket(xdict, "/W"));
        out.println("index=" + bracket(xdict, "/Index"));

        List<int[]> objstmFrames = new ArrayList<>();
        int from = 0;
        int count = 0;
        while (true) {
            int oi = s.indexOf("/Type /ObjStm", from);
            if (oi < 0) {
                oi = s.indexOf("/Type/ObjStm", from);
            }
            if (oi < 0) {
                break;
            }
            count++;
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
            for (byte by : md.digest()) {
                sha.append(String.format("%02x", by & 0xff));
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
