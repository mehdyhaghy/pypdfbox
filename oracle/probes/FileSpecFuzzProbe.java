import java.io.File;
import java.io.PrintStream;
import java.util.Arrays;
import org.apache.pdfbox.Loader;
import org.apache.pdfbox.cos.COSBase;
import org.apache.pdfbox.cos.COSDictionary;
import org.apache.pdfbox.cos.COSName;
import org.apache.pdfbox.pdmodel.PDDocument;
import org.apache.pdfbox.pdmodel.PDDocumentCatalog;
import org.apache.pdfbox.pdmodel.common.filespecification.PDComplexFileSpecification;
import org.apache.pdfbox.pdmodel.common.filespecification.PDEmbeddedFile;
import org.apache.pdfbox.pdmodel.common.filespecification.PDFileSpecification;

/**
 * Differential fuzz probe for {@link PDFileSpecification#createFS} dispatch and
 * {@link PDComplexFileSpecification} / {@link PDEmbeddedFile} parsing leniency
 * over malformed file-specification dictionaries / strings, Apache PDFBox 3.0.7
 * (wave 1514, agent B).
 *
 * <p>Complements the well-formed file-specification parity suites (round-trip
 * filename accessors, embedded-file stream + /Params date round-trips) — none of
 * which exercise the MALFORMED subset this probe targets:
 * <ul>
 *   <li>{@code createFS} dispatch: base is a {@code COSString} (simple), a
 *       {@code COSDictionary} (complex), {@code null}, or a wrong type
 *       ({@code COSName} / {@code COSInteger} / {@code COSArray} /
 *       {@code COSBoolean}) — the last group must throw {@code IOException}.</li>
 *   <li>{@code getFilename} precedence: which of {@code /UF} {@code /DOS}
 *       {@code /Mac} {@code /Unix} {@code /F} wins when several are present,
 *       some missing, some wrong-type (a name / number where a string is
 *       expected falls back to the next slot).</li>
 *   <li>{@code /EF} embedded-file sub-dictionary: {@code /F} {@code /UF}
 *       {@code /DOS} {@code /Mac} {@code /Unix} as a stream / non-stream /
 *       absent; {@code /EF} itself a non-dictionary; an empty {@code /EF}.</li>
 *   <li>embedded-file {@code /Params}: {@code /Size} {@code /CreationDate}
 *       {@code /ModDate} {@code /CheckSum} {@code /Subtype} present /
 *       wrong-type / absent.</li>
 *   <li>{@code /Desc} description present / wrong-type / absent;
 *       {@code /Type} {@code /FS} variants.</li>
 * </ul>
 *
 * <p>Driven file-based: the pypdfbox sibling
 * (tests/pdmodel/common/filespecification/oracle/test_filespec_fuzz_wave1514.py)
 * writes the deterministic corpus of one-page PDFs into a tmp directory; each
 * carries the mutated file-spec base stored in the document catalog under the
 * custom key {@code /FSProbe}, plus a {@code manifest.txt} (one case name per
 * line, in order). This probe loads each {@code <case>.pdf}, reads the catalog's
 * {@code /FSProbe} entry, dispatches it through {@code createFS}, and projects a
 * stable framed line. Both sides read the exact same bytes on disk, so the
 * construction + accessor contract is directly comparable.
 *
 * <p>Line grammar (one per case, manifest order):
 * <pre>
 *   CASE &lt;name&gt; class=&lt;simpleName|null|ERR:Exc&gt; file=&lt;F|null&gt; filename=&lt;preferred|null&gt; ef=&lt;slots|none&gt; desc=&lt;Desc|null&gt; embedded=&lt;params-projection|none&gt;
 * </pre>
 *
 * <p>{@code class} = the concrete file-spec class simple name returned by
 * {@code createFS} (or "null" when it returned null, or "ERR:&lt;Exc&gt;" when
 * it threw). {@code file} = {@code getFile()}. {@code filename} =
 * {@code getFilename()} (complex) or {@code getFile()} (simple). {@code ef} =
 * the {@code /EF} slots that resolve to an embedded-file stream, in fixed order
 * {@code F,UF,DOS,Mac,Unix} joined by {@code +} (or "none"). {@code desc} =
 * {@code getFileDescription()}. {@code embedded} = a projection of the
 * {@code /EF/F} embedded file's {@code /Params} (size, subtype, checksum
 * presence, creation/mod date presence) or "none" when there is no {@code /EF/F}
 * stream.
 */
public final class FileSpecFuzzProbe {

    static PrintStream out;

    static final COSName FS_PROBE = COSName.getPDFName("FSProbe");

    static String nz(String s) {
        return s == null ? "null" : s;
    }

    static String filenameOf(PDFileSpecification fs) {
        try {
            if (fs instanceof PDComplexFileSpecification) {
                return nz(((PDComplexFileSpecification) fs).getFilename());
            }
            return nz(fs.getFile());
        } catch (Exception e) {
            return "ERR:" + e.getClass().getSimpleName();
        }
    }

    static String efSlots(PDComplexFileSpecification fs) {
        StringBuilder sb = new StringBuilder();
        try {
            appendSlot(sb, "F", fs.getEmbeddedFile());
            appendSlotUF(sb, fs);
            appendSlot(sb, "DOS", fs.getEmbeddedFileDos());
            appendSlot(sb, "Mac", fs.getEmbeddedFileMac());
            appendSlot(sb, "Unix", fs.getEmbeddedFileUnix());
        } catch (Exception e) {
            return "ERR:" + e.getClass().getSimpleName();
        }
        return sb.length() == 0 ? "none" : sb.toString();
    }

    static void appendSlot(StringBuilder sb, String label, PDEmbeddedFile ef) {
        if (ef != null) {
            if (sb.length() > 0) {
                sb.append('+');
            }
            sb.append(label);
        }
    }

    static void appendSlotUF(StringBuilder sb, PDComplexFileSpecification fs) {
        PDEmbeddedFile ef = fs.getEmbeddedFileUnicode();
        appendSlot(sb, "UF", ef);
    }

    static String embeddedProjection(PDComplexFileSpecification fs) {
        PDEmbeddedFile ef;
        try {
            ef = fs.getEmbeddedFile();
        } catch (Exception e) {
            return "ERR:" + e.getClass().getSimpleName();
        }
        if (ef == null) {
            return "none";
        }
        StringBuilder sb = new StringBuilder();
        try {
            sb.append("size=").append(ef.getSize());
        } catch (Exception e) {
            sb.append("size=ERR:").append(e.getClass().getSimpleName());
        }
        try {
            sb.append(",subtype=").append(nz(ef.getSubtype()));
        } catch (Exception e) {
            sb.append(",subtype=ERR:").append(e.getClass().getSimpleName());
        }
        try {
            sb.append(",cksum=").append(ef.getCheckSum() == null ? "absent" : "present");
        } catch (Exception e) {
            sb.append(",cksum=ERR:").append(e.getClass().getSimpleName());
        }
        try {
            sb.append(",cdate=").append(ef.getCreationDate() == null ? "absent" : "present");
        } catch (Exception e) {
            sb.append(",cdate=ERR:").append(e.getClass().getSimpleName());
        }
        try {
            sb.append(",mdate=").append(ef.getModDate() == null ? "absent" : "present");
        } catch (Exception e) {
            sb.append(",mdate=ERR:").append(e.getClass().getSimpleName());
        }
        return sb.toString();
    }

    static void runCase(File dir, String name) {
        File pdf = new File(dir, name + ".pdf");
        StringBuilder sb = new StringBuilder();
        sb.append("CASE ").append(name).append(' ');
        PDDocument doc = null;
        try {
            doc = Loader.loadPDF(pdf);
            PDDocumentCatalog cat = doc.getDocumentCatalog();
            COSDictionary catDict = cat.getCOSObject();
            COSBase base = catDict.getDictionaryObject(FS_PROBE);
            PDFileSpecification fs;
            try {
                fs = PDFileSpecification.createFS(base);
            } catch (Exception e) {
                sb.append("class=ERR:").append(e.getClass().getSimpleName());
                sb.append(" file=ERR filename=ERR ef=ERR desc=ERR embedded=ERR");
                out.println(sb.toString());
                return;
            }
            if (fs == null) {
                sb.append("class=null file=null filename=null "
                        + "ef=none desc=null embedded=none");
                out.println(sb.toString());
                return;
            }
            sb.append("class=").append(fs.getClass().getSimpleName());
            String file;
            try {
                file = nz(fs.getFile());
            } catch (Exception e) {
                file = "ERR:" + e.getClass().getSimpleName();
            }
            sb.append(" file=").append(file);
            sb.append(" filename=").append(filenameOf(fs));
            if (fs instanceof PDComplexFileSpecification) {
                PDComplexFileSpecification cfs = (PDComplexFileSpecification) fs;
                sb.append(" ef=").append(efSlots(cfs));
                String desc;
                try {
                    desc = nz(cfs.getFileDescription());
                } catch (Exception e) {
                    desc = "ERR:" + e.getClass().getSimpleName();
                }
                sb.append(" desc=").append(desc);
                sb.append(" embedded=").append(embeddedProjection(cfs));
            } else {
                sb.append(" ef=none desc=null embedded=none");
            }
        } catch (Exception e) {
            sb.append("class=ERR:").append(e.getClass().getSimpleName());
            sb.append(" file=ERR filename=ERR ef=ERR desc=ERR embedded=ERR");
        } finally {
            if (doc != null) {
                try {
                    doc.close();
                } catch (Exception ignored) {
                    // best-effort close
                }
            }
        }
        out.println(sb.toString());
    }

    public static void main(String[] args) throws Exception {
        out = new PrintStream(System.out, true, "UTF-8");
        File dir = new File(args[0]);
        File manifest = new File(dir, "manifest.txt");
        String[] names =
                new String(java.nio.file.Files.readAllBytes(manifest.toPath()),
                                java.nio.charset.StandardCharsets.UTF_8)
                        .split("\n");
        Arrays.stream(names)
                .map(String::trim)
                .filter(s -> !s.isEmpty())
                .forEach(name -> runCase(dir, name));
    }
}
