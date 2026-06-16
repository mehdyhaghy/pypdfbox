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
import org.apache.pdfbox.cos.COSArray;
import org.apache.pdfbox.cos.COSName;
import org.apache.pdfbox.pdmodel.PDDocument;
import org.apache.pdfbox.pdmodel.PDDocumentCatalog;
import org.apache.pdfbox.pdmodel.PDDocumentInformation;
import org.apache.pdfbox.pdmodel.PDPage;
import org.apache.pdfbox.pdmodel.PDPageContentStream;
import org.apache.pdfbox.pdmodel.common.PDRectangle;
import org.apache.pdfbox.pdmodel.font.PDType1Font;
import org.apache.pdfbox.pdmodel.font.Standard14Fonts;
import org.apache.pdfbox.pdmodel.interactive.annotation.PDAnnotation;
import org.apache.pdfbox.pdmodel.interactive.annotation.PDAnnotationText;

/**
 * Live oracle probe for the <b>object-SELECTION</b> contract of an incremental
 * save: which objects land in the appended section, what the appended trailer
 * says, and whether the original bytes survive as a verbatim prefix.
 *
 * Earlier incremental probes pinned single facets: the /Prev chain
 * (IncrementalChainProbe), the exact dirty set for one /Info edit
 * (IncrementalXrefDeltaProbe), a single added annotation
 * (IncrementalAddAnnotationProbe), the trailing %%EOF bytes
 * (IncrementalTailBytesProbe), and the appended-xref-stream shape
 * (IncrementalXrefStreamShapeProbe). This probe sweeps a *matrix* of distinct
 * mutation kinds and projects, for each, the shape a parity test compares:
 *
 *   - the SET of object numbers written in the appended section (only dirty
 *     objects + the new xref machinery; never a re-dump of the pool),
 *   - the appended trailer's /Prev (== source last startxref) and /Size,
 *   - prefix preservation (the increment is appended, not a rewrite),
 *   - reload-after-increment recovers the mutation.
 *
 * Modes (args[0]):
 *
 *   editinfo   in out      mutate /Info /Title (in-place edit of an existing obj)
 *   addannot   in out      add a text annotation to page 0 (mints a new obj)
 *   editpage   in out      append a content stream to page 0 (edits page + new obj)
 *   catalogkey in out      set a catalog key (/Lang) on the existing /Root
 *   noop       in out      save_incremental with nothing dirty (minimal/empty)
 *   chain2     in out      two sequential increments (two /Prev hops)
 *
 * Output is line-oriented UTF-8 key=value. The appended-object set is the
 * comma-joined sorted object numbers carrying a used ('n') entry in the
 * appended classic xref table, OR the /Index pairs of an appended xref stream,
 * with object 0 and the xref-stream's own object number dropped.
 */
public final class IncrementalSelectionFuzzProbe {

    private static String nz(String v) {
        return v == null ? "NULL" : v;
    }

    /** Last startxref integer in the file (offset of its final xref). */
    private static long lastStartxref(byte[] bytes) {
        String s = new String(bytes, StandardCharsets.ISO_8859_1);
        Matcher m = Pattern.compile("startxref\\s+(\\d+)").matcher(s);
        long last = -1;
        while (m.find()) {
            last = Long.parseLong(m.group(1));
        }
        return last;
    }

    /** /Prev integer parsed from the section appended after byte {@code from}. */
    private static long appendedPrev(byte[] bytes, int from) {
        if (from >= bytes.length) {
            return -1;
        }
        String tail = new String(bytes, from, bytes.length - from,
                StandardCharsets.ISO_8859_1);
        Matcher m = Pattern.compile("/Prev\\s+(\\d+)").matcher(tail);
        long last = -1;
        while (m.find()) {
            last = Long.parseLong(m.group(1));
        }
        return last;
    }

    /** /Size integer parsed from the appended trailer (section after from). */
    private static long appendedSize(byte[] bytes, int from) {
        if (from >= bytes.length) {
            return -1;
        }
        String tail = new String(bytes, from, bytes.length - from,
                StandardCharsets.ISO_8859_1);
        Matcher m = Pattern.compile("/Size\\s+(\\d+)").matcher(tail);
        long last = -1;
        while (m.find()) {
            last = Long.parseLong(m.group(1));
        }
        return last;
    }

    /**
     * The set of data object numbers the appended increment wrote: classic
     * 'n' entries OR xref-stream /Index pairs, minus object 0 and the
     * xref-stream's own object number. Returns an empty set when nothing was
     * appended (no-op).
     */
    private static TreeSet<Integer> appendedDataObjs(byte[] bytes, int from) {
        TreeSet<Integer> classic = usedObjsInSection(bytes, from);
        if (classic != null && !classic.isEmpty()) {
            classic.remove(0);
            return classic;
        }
        if (from >= bytes.length) {
            return new TreeSet<>();
        }
        String tail = new String(bytes, from, bytes.length - from,
                StandardCharsets.ISO_8859_1);
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
            for (int i = 0; i + 1 < nums.length; i += 2) {
                if (nums[i].isEmpty()) {
                    continue;
                }
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

    private static TreeSet<Integer> usedObjsInSection(byte[] bytes, int from) {
        if (from >= bytes.length) {
            return null;
        }
        String tail = new String(bytes, from, bytes.length - from,
                StandardCharsets.ISO_8859_1);
        Matcher xm = Pattern.compile("(?:^|\\r|\\n)xref\\s*\\r?\\n\\d+\\s+\\d+")
                .matcher(tail);
        if (!xm.find()) {
            return null;
        }
        int xi = tail.indexOf("xref", xm.start());
        int trailerAt = tail.indexOf("trailer", xi);
        String section = trailerAt >= 0 ? tail.substring(xi, trailerAt)
                : tail.substring(xi);
        String body = section.substring("xref".length());
        Matcher header = Pattern.compile("(\\d+)\\s+(\\d+)\\s*\\r?\\n")
                .matcher(body);
        List<int[]> headers = new ArrayList<>();
        while (header.find()) {
            headers.add(new int[]{
                    Integer.parseInt(header.group(1)),
                    Integer.parseInt(header.group(2))});
        }
        List<String> flags = new ArrayList<>();
        Matcher e2 = Pattern.compile("(\\d{10})\\s(\\d{5})\\s([nf])")
                .matcher(body);
        while (e2.find()) {
            flags.add(e2.group(3));
        }
        TreeSet<Integer> used = new TreeSet<>();
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

    private static String joinSet(TreeSet<Integer> objs) {
        StringBuilder sb = new StringBuilder();
        for (int n : objs) {
            if (sb.length() > 0) {
                sb.append(",");
            }
            sb.append(n);
        }
        return sb.toString();
    }

    /** Count of "startxref" markers in the raw bytes (revision count). */
    private static int countStartxref(byte[] bytes) {
        String s = new String(bytes, StandardCharsets.ISO_8859_1);
        Matcher m = Pattern.compile("startxref").matcher(s);
        int n = 0;
        while (m.find()) {
            n++;
        }
        return n;
    }

    /** Apply the named mutation to the loaded document. */
    private static void mutate(String mode, PDDocument doc) throws Exception {
        switch (mode) {
            case "editinfo": {
                PDDocumentInformation info = doc.getDocumentInformation();
                info.setTitle("SelTitle");
                info.getCOSObject().setNeedToBeUpdated(true);
                break;
            }
            case "addannot": {
                PDPage page = doc.getPage(0);
                PDAnnotationText annot = new PDAnnotationText();
                annot.setContents("SelAnnot");
                annot.setRectangle(new PDRectangle(50, 50, 100, 100));
                List<PDAnnotation> annots = page.getAnnotations();
                annots.add(annot);
                page.setAnnotations(annots);
                annot.getCOSObject().setNeedToBeUpdated(true);
                page.getCOSObject().setNeedToBeUpdated(true);
                break;
            }
            case "editpage": {
                PDPage page = doc.getPage(0);
                try (PDPageContentStream cs = new PDPageContentStream(
                        doc, page, PDPageContentStream.AppendMode.APPEND,
                        true, true)) {
                    cs.beginText();
                    cs.setFont(new PDType1Font(
                            Standard14Fonts.FontName.HELVETICA), 12);
                    cs.newLineAtOffset(72, 72);
                    cs.showText("SelEdit");
                    cs.endText();
                }
                page.getCOSObject().setNeedToBeUpdated(true);
                break;
            }
            case "catalogkey": {
                PDDocumentCatalog cat = doc.getDocumentCatalog();
                cat.setLanguage("en-US");
                cat.getCOSObject().setNeedToBeUpdated(true);
                break;
            }
            case "noop": {
                // Nothing dirty — exercise the empty-increment path.
                break;
            }
            default:
                throw new IllegalArgumentException("unknown mode: " + mode);
        }
    }

    public static void main(String[] args) throws Exception {
        String mode = args[0];
        File src = new File(args[1]);
        File out = new File(args[2]);
        byte[] srcBytes = Files.readAllBytes(src.toPath());
        int srcLen = srcBytes.length;
        long srcStartxref = lastStartxref(srcBytes);
        int srcSections = countStartxref(srcBytes);

        StringBuilder sb = new StringBuilder();
        sb.append("mode=").append(mode).append("\n");
        sb.append("source_len=").append(srcLen).append("\n");
        sb.append("source_startxref=").append(srcStartxref).append("\n");
        sb.append("source_sections=").append(srcSections).append("\n");

        if ("chain2".equals(mode)) {
            // Two sequential increments on top of the source: rev1 edits
            // /Info /Title, rev2 sets a catalog key. Each appends a /Prev hop.
            File mid = new File(out.getPath() + ".mid");
            try (PDDocument doc = Loader.loadPDF(src)) {
                doc.getDocumentInformation().setTitle("Sel1");
                doc.getDocumentInformation().getCOSObject()
                        .setNeedToBeUpdated(true);
                try (FileOutputStream os = new FileOutputStream(mid)) {
                    doc.saveIncremental(os);
                }
            }
            byte[] midBytes = Files.readAllBytes(mid.toPath());
            long midStartxref = lastStartxref(midBytes);
            try (PDDocument doc = Loader.loadPDF(mid)) {
                doc.getDocumentCatalog().setLanguage("de-DE");
                doc.getDocumentCatalog().getCOSObject()
                        .setNeedToBeUpdated(true);
                try (FileOutputStream os = new FileOutputStream(out)) {
                    doc.saveIncremental(os);
                }
            }
            byte[] outBytes = Files.readAllBytes(out.toPath());
            sb.append("mid_len=").append(midBytes.length).append("\n");
            sb.append("mid_startxref=").append(midStartxref).append("\n");
            sb.append("mid_prefix_ok=")
                    .append(startsWith(midBytes, srcBytes)).append("\n");
            sb.append("out_prefix_ok=")
                    .append(startsWith(outBytes, midBytes)).append("\n");
            // rev1's /Prev must point at the source xref; rev2's at rev1's.
            sb.append("rev1_prev=")
                    .append(appendedPrev(midBytes, srcLen)).append("\n");
            sb.append("rev1_prev_matches=")
                    .append(appendedPrev(midBytes, srcLen) == srcStartxref)
                    .append("\n");
            sb.append("rev2_prev=")
                    .append(appendedPrev(outBytes, midBytes.length)).append("\n");
            sb.append("rev2_prev_matches=")
                    .append(appendedPrev(outBytes, midBytes.length)
                            == midStartxref)
                    .append("\n");
            sb.append("out_sections=")
                    .append(countStartxref(outBytes)).append("\n");
            // Both edits survive the chain.
            try (PDDocument doc = Loader.loadPDF(out)) {
                sb.append("title=")
                        .append(nz(doc.getDocumentInformation().getTitle()))
                        .append("\n");
                sb.append("lang=")
                        .append(nz(doc.getDocumentCatalog().getLanguage()))
                        .append("\n");
            }
            mid.delete();
            System.out.print(sb);
            return;
        }

        // Single-increment modes.
        try (PDDocument doc = Loader.loadPDF(src)) {
            mutate(mode, doc);
            try (FileOutputStream os = new FileOutputStream(out)) {
                doc.saveIncremental(os);
            }
        }

        byte[] outBytes = Files.readAllBytes(out.toPath());
        boolean prefixOk = startsWith(outBytes, srcBytes);
        boolean appended = outBytes.length > srcLen;
        TreeSet<Integer> objs = appendedDataObjs(outBytes, srcLen);
        long prev = appendedPrev(outBytes, srcLen);
        long size = appendedSize(outBytes, srcLen);

        sb.append("out_len=").append(outBytes.length).append("\n");
        sb.append("prefix_ok=").append(prefixOk).append("\n");
        sb.append("appended=").append(appended).append("\n");
        sb.append("appended_objs=").append(joinSet(objs)).append("\n");
        sb.append("appended_obj_count=").append(objs.size()).append("\n");
        sb.append("appended_prev=").append(prev).append("\n");
        sb.append("prev_matches=").append(prev == srcStartxref).append("\n");
        sb.append("appended_size=").append(size).append("\n");
        sb.append("out_sections=")
                .append(countStartxref(outBytes)).append("\n");

        // Reload-after-increment recovers the mutation.
        try (PDDocument doc = Loader.loadPDF(out)) {
            sb.append("reload_pages=")
                    .append(doc.getNumberOfPages()).append("\n");
            sb.append("reload_title=")
                    .append(nz(doc.getDocumentInformation().getTitle()))
                    .append("\n");
            sb.append("reload_lang=")
                    .append(nz(doc.getDocumentCatalog().getLanguage()))
                    .append("\n");
            int annotCount = 0;
            COSArray a = (COSArray) doc.getPage(0).getCOSObject()
                    .getDictionaryObject(COSName.ANNOTS);
            if (a != null) {
                annotCount = a.size();
            }
            sb.append("reload_annots=").append(annotCount).append("\n");
        }
        System.out.print(sb);
    }

    private static boolean startsWith(byte[] whole, byte[] prefix) {
        if (whole.length < prefix.length) {
            return false;
        }
        for (int i = 0; i < prefix.length; i++) {
            if (whole[i] != prefix[i]) {
                return false;
            }
        }
        return true;
    }
}
