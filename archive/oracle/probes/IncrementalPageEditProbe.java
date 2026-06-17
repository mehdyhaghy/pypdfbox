import java.io.ByteArrayOutputStream;
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
import org.apache.pdfbox.cos.COSDictionary;
import org.apache.pdfbox.cos.COSName;
import org.apache.pdfbox.pdmodel.PDDocument;
import org.apache.pdfbox.pdmodel.PDPage;
import org.apache.pdfbox.pdmodel.common.PDRectangle;

/**
 * Probe: which objects land in the appended increment when ONE page's
 * /MediaBox is changed.
 *
 * Modes (args[0]):
 *   mediabox-page-only   src out   -- mutate page 0 MediaBox, mark ONLY the page dict dirty
 *   mediabox-chain       src out   -- mutate page 0 MediaBox, mark page + pages-tree + catalog dirty
 *   add-annot            src out   -- add a Link annotation to page 0, mark page dirty
 *   unmodified           src out   -- saveIncremental with NO change at all
 *
 * Emits the sorted set of used object numbers in the appended xref section
 * (object 0 and any appended xref-stream object dropped), plus appended_len.
 */
public final class IncrementalPageEditProbe {

    private static long lastStartxref(byte[] b) {
        String s = new String(b, StandardCharsets.ISO_8859_1);
        Matcher m = Pattern.compile("startxref\\s+(\\d+)").matcher(s);
        long last = -1;
        while (m.find()) last = Long.parseLong(m.group(1));
        return last;
    }

    private static TreeSet<Integer> usedObjs(byte[] bytes, int from) {
        String tail = new String(bytes, from, bytes.length - from, StandardCharsets.ISO_8859_1);
        Matcher xm = Pattern.compile("(?:^|\\r|\\n)xref\\s*\\r?\\n\\d+\\s+\\d+").matcher(tail);
        TreeSet<Integer> used = new TreeSet<>();
        if (xm.find()) {
            int xi = tail.indexOf("xref", xm.start());
            int trailerAt = tail.indexOf("trailer", xi);
            String section = trailerAt >= 0 ? tail.substring(xi, trailerAt) : tail.substring(xi);
            String body = section.substring("xref".length());
            Matcher header = Pattern.compile("(\\d+)\\s+(\\d+)\\s*\\r?\\n").matcher(body);
            List<int[]> headers = new ArrayList<>();
            while (header.find()) {
                headers.add(new int[]{Integer.parseInt(header.group(1)), Integer.parseInt(header.group(2))});
            }
            List<String> flags = new ArrayList<>();
            Matcher e2 = Pattern.compile("(\\d{10})\\s(\\d{5})\\s([nf])").matcher(body);
            while (e2.find()) flags.add(e2.group(3));
            int idx = 0;
            for (int[] h : headers) {
                int first = h[0], count = h[1];
                for (int k = 0; k < count && idx < flags.size(); k++, idx++) {
                    if ("n".equals(flags.get(idx))) used.add(first + k);
                }
            }
            used.remove(0);
            return used;
        }
        // xref stream: parse /Index
        Matcher xrefObj = Pattern.compile("(\\d+)\\s+\\d+\\s+obj\\b(?=[^e]*?/Type\\s*/XRef)", Pattern.DOTALL).matcher(tail);
        int xrefOwn = -1;
        if (xrefObj.find()) xrefOwn = Integer.parseInt(xrefObj.group(1));
        Matcher idxm = Pattern.compile("/Index\\s*\\[([^\\]]*)\\]").matcher(tail);
        if (idxm.find()) {
            String[] nums = idxm.group(1).trim().split("\\s+");
            for (int i = 0; i + 1 < nums.length; i += 2) {
                int first = Integer.parseInt(nums[i]);
                int count = Integer.parseInt(nums[i + 1]);
                for (int k = 0; k < count; k++) used.add(first + k);
            }
        }
        used.remove(0);
        if (xrefOwn >= 0) used.remove(xrefOwn);
        return used;
    }

    public static void main(String[] args) throws Exception {
        String mode = args[0];
        java.io.File src = new java.io.File(args[1]);
        java.io.File out = new java.io.File(args[2]);
        byte[] srcBytes = Files.readAllBytes(src.toPath());
        int srcLen = srcBytes.length;
        long srcStartxref = lastStartxref(srcBytes);

        String saveError = "";
        try (PDDocument doc = Loader.loadPDF(src)) {
            PDPage page = doc.getPage(0);
            COSDictionary pageDict = page.getCOSObject();
            switch (mode) {
                case "mediabox-page-only": {
                    page.setMediaBox(new PDRectangle(0, 0, 333, 444));
                    pageDict.setNeedToBeUpdated(true);
                    break;
                }
                case "mediabox-chain": {
                    page.setMediaBox(new PDRectangle(0, 0, 333, 444));
                    pageDict.setNeedToBeUpdated(true);
                    COSDictionary parent = pageDict.getCOSDictionary(COSName.PARENT);
                    while (parent != null) {
                        parent.setNeedToBeUpdated(true);
                        parent = parent.getCOSDictionary(COSName.PARENT);
                    }
                    doc.getDocumentCatalog().getCOSObject().setNeedToBeUpdated(true);
                    break;
                }
                case "add-annot": {
                    org.apache.pdfbox.pdmodel.interactive.annotation.PDAnnotationLink link =
                        new org.apache.pdfbox.pdmodel.interactive.annotation.PDAnnotationLink();
                    link.setRectangle(new PDRectangle(10, 10, 50, 50));
                    page.getAnnotations().add(link);
                    pageDict.setNeedToBeUpdated(true);
                    pageDict.getCOSArray(COSName.ANNOTS).setNeedToBeUpdated(true);
                    break;
                }
                case "unmodified":
                    break;
                default:
                    throw new IllegalArgumentException("mode: " + mode);
            }
            try (FileOutputStream os = new FileOutputStream(out)) {
                doc.saveIncremental(os);
            } catch (Exception e) {
                saveError = e.getClass().getSimpleName() + ":" + e.getMessage();
            }
        }

        byte[] outBytes = Files.readAllBytes(out.toPath());
        int appendedLen = outBytes.length - srcLen;
        boolean prefixOk = appendedLen >= 0;
        if (prefixOk) {
            for (int i = 0; i < srcLen; i++) {
                if (outBytes[i] != srcBytes[i]) { prefixOk = false; break; }
            }
        }
        TreeSet<Integer> used = usedObjs(outBytes, srcLen);
        long prev = -1;
        {
            String tail = new String(outBytes, srcLen, Math.max(0, outBytes.length - srcLen), StandardCharsets.ISO_8859_1);
            Matcher m = Pattern.compile("/Prev\\s+(\\d+)").matcher(tail);
            while (m.find()) prev = Long.parseLong(m.group(1));
        }
        boolean srcIsXrefStream;
        {
            String s = new String(srcBytes, StandardCharsets.ISO_8859_1);
            int last = s.lastIndexOf("startxref");
            // crude: does the section right after last startxref's target use a table?
            srcIsXrefStream = s.contains("/Type/XRef") || s.contains("/Type /XRef");
        }
        boolean incrUsesXrefStream;
        {
            String tail = new String(outBytes, srcLen, Math.max(0, outBytes.length - srcLen), StandardCharsets.ISO_8859_1);
            incrUsesXrefStream = tail.contains("/Type/XRef") || tail.contains("/Type /XRef");
        }

        StringBuilder objs = new StringBuilder();
        for (int n : used) {
            if (objs.length() > 0) objs.append(",");
            objs.append(n);
        }

        StringBuilder sb = new StringBuilder();
        sb.append("mode=").append(mode).append("\n");
        sb.append("source_len=").append(srcLen).append("\n");
        sb.append("appended_len=").append(appendedLen).append("\n");
        sb.append("prefix_preserved=").append(prefixOk).append("\n");
        sb.append("used_objs=").append(objs).append("\n");
        sb.append("used_count=").append(used.size()).append("\n");
        sb.append("appended_prev=").append(prev).append("\n");
        sb.append("prev_matches=").append(prev == srcStartxref).append("\n");
        sb.append("src_xref_stream=").append(srcIsXrefStream).append("\n");
        sb.append("incr_xref_stream=").append(incrUsesXrefStream).append("\n");
        sb.append("save_error=").append(saveError.isEmpty() ? "NONE" : saveError).append("\n");
        System.out.print(sb);
    }
}
