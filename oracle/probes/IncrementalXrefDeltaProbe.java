import java.io.File;
import java.io.FileOutputStream;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.util.ArrayList;
import java.util.List;
import java.util.TreeSet;
import java.util.regex.Matcher;
import java.util.regex.Pattern;
import org.apache.pdfbox.Loader;
import org.apache.pdfbox.pdmodel.PDDocument;
import org.apache.pdfbox.pdmodel.PDDocumentInformation;

/**
 * Live oracle probe pinning the two hard invariants of an incremental save's
 * appended cross-reference section (PDF 32000-1 §7.5.6):
 *
 *  1. ONLY the dirty/changed objects (plus the mandatory free-list head,
 *     object 0) appear in the appended xref section. The increment must NOT
 *     re-emit unchanged objects — that would defeat the append-only model.
 *  2. The appended trailer's {@code /Prev} numerically equals the source's
 *     last {@code startxref} offset (the byte offset of the previous xref),
 *     so a parser can walk the chain backwards.
 *
 * Modes (args[0]):
 *
 *   delta  in.pdf out.pdf
 *       Load in.pdf, mutate /Info /Title to "DeltaTitle", flag the /Info dict
 *       (and trailer) dirty, saveIncremental to out.pdf. Then parse out.pdf's
 *       raw bytes — the section APPENDED after the source's length — and emit:
 *
 *         source_len        = length in bytes of the original file
 *         source_startxref  = the source's last startxref offset (the /Prev
 *                             target the increment must point at)
 *         appended_prev     = the /Prev value parsed from the appended trailer
 *         prev_matches      = appended_prev == source_startxref
 *         appended_used_objs= comma-joined, sorted object numbers carrying a
 *                             "used" (n) entry in the appended xref section
 *         appended_obj_count= count of those used entries
 *         title             = /Info /Title read back after reload
 *
 * The appended xref section is located by scanning the bytes from
 * {@code source_len} onward for the first {@code xref} keyword, then reading
 * each {@code first count} subsection header and its entries. Only the
 * appended section is inspected so the metric is exactly "what this one
 * increment wrote", independent of how many revisions preceded it.
 */
public final class IncrementalXrefDeltaProbe {

    private static String nz(String v) {
        return v == null ? "NULL" : v;
    }

    /** Last startxref integer in the file (the offset of its final xref). */
    private static long lastStartxref(byte[] bytes) {
        String s = new String(bytes, StandardCharsets.ISO_8859_1);
        Matcher m = Pattern.compile("startxref\\s+(\\d+)").matcher(s);
        long last = -1;
        while (m.find()) {
            last = Long.parseLong(m.group(1));
        }
        return last;
    }

    /**
     * The set of <i>data</i> object numbers the appended increment wrote —
     * the changed/added objects a parity test compares across engines,
     * independent of xref encoding. We derive it from whatever the increment
     * used:
     *
     *   - classic appended table  → the object numbers with a used ('n') entry
     *   - appended xref *stream*   → the object numbers in the stream's /Index
     *
     * In both cases we drop object 0 (the mandatory free-list head) and the
     * object number of the appended xref stream itself (a stream-encoding
     * artefact that a classic-table writer does not need), leaving exactly the
     * application-level objects the increment modified.
     */
    private static TreeSet<Integer> dirtyDataObjs(byte[] bytes, int from) {
        TreeSet<Integer> classic = usedObjsInSection(bytes, from);
        if (classic != null && !classic.isEmpty()) {
            classic.remove(0);
            return classic;
        }
        // No classic table — parse the appended xref stream's /Index pairs.
        String tail = new String(bytes, from, bytes.length - from,
                StandardCharsets.ISO_8859_1);
        // The xref stream is itself an indirect object: "<num> 0 obj ... /Type
        // /XRef ... /Index [ ... ]". Capture the xref stream's own object
        // number so we can exclude it.
        Matcher xrefObj = Pattern.compile(
                "(\\d+)\\s+\\d+\\s+obj\\b(?=[^e]*?/Type\\s*/XRef)",
                Pattern.DOTALL).matcher(tail);
        int xrefOwnNum = -1;
        if (xrefObj.find()) {
            xrefOwnNum = Integer.parseInt(xrefObj.group(1));
        }
        Matcher idx = Pattern.compile("/Index\\s*\\[([^\\]]*)\\]").matcher(tail);
        TreeSet<Integer> objs = new TreeSet<>();
        if (idx.find()) {
            String[] nums = idx.group(1).trim().split("\\s+");
            // /Index is a sequence of (first, count) pairs.
            for (int i = 0; i + 1 < nums.length; i += 2) {
                int first = Integer.parseInt(nums[i]);
                int count = Integer.parseInt(nums[i + 1]);
                for (int k = 0; k < count; k++) {
                    objs.add(first + k);
                }
            }
        }
        objs.remove(0);
        if (xrefOwnNum >= 0) {
            objs.remove(xrefOwnNum);
        }
        return objs;
    }

    /**
     * Parse the classic xref section beginning at byte {@code from}, returning
     * the sorted set of object numbers that carry a used ('n') entry. Returns
     * null when no {@code xref} keyword (a stream-based increment) is found.
     */
    private static TreeSet<Integer> usedObjsInSection(byte[] bytes, int from) {
        String tail = new String(bytes, from, bytes.length - from,
                StandardCharsets.ISO_8859_1);
        // Match a classic table opener: "xref" on its own followed by a
        // subsection header. Avoid matching the "xref" inside "startxref".
        Matcher xm = Pattern.compile("(?:^|\\r|\\n)xref\\s*\\r?\\n\\d+\\s+\\d+")
                .matcher(tail);
        if (!xm.find()) {
            return null;
        }
        int xi = tail.indexOf("xref", xm.start());
        // Bound the scan at the trailer keyword so a later revision's xref
        // (there is none after this one in our single-append case, but be
        // strict) cannot bleed in.
        int trailerAt = tail.indexOf("trailer", xi);
        String section = trailerAt >= 0 ? tail.substring(xi, trailerAt)
                : tail.substring(xi);
        // After the "xref" keyword come repeating "first count" headers then
        // 20-byte entries "oooooooooo ggggg n|f".
        String body = section.substring("xref".length());
        Matcher header = Pattern.compile(
                "(\\d+)\\s+(\\d+)\\s*\\r?\\n").matcher(body);
        Matcher entry = Pattern.compile(
                "(\\d{10})\\s(\\d{5})\\s([nf])").matcher(body);
        TreeSet<Integer> used = new TreeSet<>();
        // Re-derive object numbers by walking headers in order and consuming
        // the corresponding number of entries from a flat entry list.
        List<int[]> headers = new ArrayList<>();
        while (header.find()) {
            headers.add(new int[]{
                    Integer.parseInt(header.group(1)),
                    Integer.parseInt(header.group(2))});
        }
        List<String> flags = new ArrayList<>();
        List<Integer> firstStarts = new ArrayList<>();
        Matcher e2 = Pattern.compile(
                "(\\d{10})\\s(\\d{5})\\s([nf])").matcher(body);
        while (e2.find()) {
            flags.add(e2.group(3));
        }
        int idx = 0;
        for (int[] h : headers) {
            int first = h[0];
            int count = h[1];
            for (int k = 0; k < count && idx < flags.size(); k++, idx++) {
                if ("n".equals(flags.get(idx))) {
                    used.add(first + k);
                }
            }
        }
        return used;
    }

    /** /Prev integer parsed from the appended trailer (section after from). */
    private static long appendedPrev(byte[] bytes, int from) {
        String tail = new String(bytes, from, bytes.length - from,
                StandardCharsets.ISO_8859_1);
        Matcher m = Pattern.compile("/Prev\\s+(\\d+)").matcher(tail);
        long last = -1;
        while (m.find()) {
            last = Long.parseLong(m.group(1));
        }
        return last;
    }

    public static void main(String[] args) throws Exception {
        String mode = args[0];
        if (!"delta".equals(mode)) {
            throw new IllegalArgumentException("unknown mode: " + mode);
        }
        File src = new File(args[1]);
        File out = new File(args[2]);
        byte[] srcBytes = Files.readAllBytes(src.toPath());
        int srcLen = srcBytes.length;
        long srcStartxref = lastStartxref(srcBytes);

        try (PDDocument doc = Loader.loadPDF(src)) {
            PDDocumentInformation info = doc.getDocumentInformation();
            info.setTitle("DeltaTitle");
            info.getCOSObject().setNeedToBeUpdated(true);
            try (FileOutputStream os = new FileOutputStream(out)) {
                doc.saveIncremental(os);
            }
        }

        byte[] outBytes = Files.readAllBytes(out.toPath());
        TreeSet<Integer> used = dirtyDataObjs(outBytes, srcLen);
        long prev = appendedPrev(outBytes, srcLen);

        StringBuilder objs = new StringBuilder();
        int objCount = 0;
        if (used != null) {
            for (int n : used) {
                if (objs.length() > 0) {
                    objs.append(",");
                }
                objs.append(n);
                objCount++;
            }
        }

        String title;
        try (PDDocument doc = Loader.loadPDF(out)) {
            title = doc.getDocumentInformation().getTitle();
        }

        StringBuilder sb = new StringBuilder();
        sb.append("source_len=").append(srcLen).append("\n");
        sb.append("source_startxref=").append(srcStartxref).append("\n");
        sb.append("appended_prev=").append(prev).append("\n");
        sb.append("prev_matches=").append(prev == srcStartxref).append("\n");
        sb.append("appended_used_objs=").append(objs).append("\n");
        sb.append("appended_obj_count=").append(objCount).append("\n");
        sb.append("title=").append(nz(title)).append("\n");
        System.out.print(sb);
    }
}
