import java.io.ByteArrayInputStream;
import java.io.ByteArrayOutputStream;
import java.io.File;
import java.io.InputStream;
import java.io.OutputStream;
import java.io.PrintStream;
import java.math.BigInteger;
import java.nio.file.Files;
import java.security.KeyPair;
import java.security.KeyPairGenerator;
import java.security.PrivateKey;
import java.security.Security;
import java.security.cert.X509Certificate;
import java.util.Calendar;
import java.util.Date;
import java.util.List;

import org.apache.pdfbox.Loader;
import org.apache.pdfbox.cos.COSName;
import org.apache.pdfbox.pdmodel.PDDocument;
import org.apache.pdfbox.pdmodel.PDPage;
import org.apache.pdfbox.pdmodel.interactive.digitalsignature.PDSignature;
import org.apache.pdfbox.pdmodel.interactive.digitalsignature.SignatureInterface;
import org.apache.pdfbox.pdmodel.interactive.digitalsignature.SignatureOptions;

import org.bouncycastle.asn1.x500.X500Name;
import org.bouncycastle.cert.X509CertificateHolder;
import org.bouncycastle.cert.jcajce.JcaCertStore;
import org.bouncycastle.cert.jcajce.JcaX509CertificateConverter;
import org.bouncycastle.cert.jcajce.JcaX509v3CertificateBuilder;
import org.bouncycastle.cms.CMSSignedData;
import org.bouncycastle.cms.CMSSignedDataGenerator;
import org.bouncycastle.cms.CMSTypedData;
import org.bouncycastle.cms.CMSProcessableByteArray;
import org.bouncycastle.cms.jcajce.JcaSignerInfoGeneratorBuilder;
import org.bouncycastle.jce.provider.BouncyCastleProvider;
import org.bouncycastle.operator.ContentSigner;
import org.bouncycastle.operator.jcajce.JcaContentSignerBuilder;
import org.bouncycastle.operator.jcajce.JcaDigestCalculatorProviderBuilder;

/**
 * Live oracle probe: fuzz the SAVE-TIME /ByteRange + /Contents placeholder
 * computation that Apache PDFBox performs inside
 * {@code PDDocument.addSignature(...)} + {@code saveIncremental(...)}.
 *
 * Wave 1538 fuzzed seed values and wave 1551 the PDSignature dict accessors;
 * this probe targets the bytes the COSWriter actually lays down when reserving
 * the signature placeholder and computing the four /ByteRange integers — the
 * arithmetic that wires the digest window around the /Contents hex token.
 *
 * For each configuration it self-builds a tiny PDF in memory (so no fixture is
 * needed), signs it, incrementally saves it, then reloads the signed bytes and
 * projects the structural facts a parity test compares against pypdfbox:
 *
 *   case.<i>.label=<name>
 *   case.<i>.sigCount=<number of signature dicts after save>
 *   case.<i>.byterange=a,b,c,d
 *   case.<i>.fileLength=<signed file size in bytes>
 *   case.<i>.contentsHexLen=<chars between `<` and `>` of /Contents>
 *   case.<i>.gap=<c - (a+b)>   (== contentsHexLen + 2, the `<` `>` delimiters)
 *   case.<i>.gapEqualsHexPlusTwo=<true|false>
 *   case.<i>.coversWholeFileExceptContents=<true|false>  (a==0, c+d==fileLen)
 *   case.<i>.loadable=<true>   (reload succeeded)
 *
 * Configurations (~18): default /Contents size; explicit preferred sizes
 * 4096 / 12000 / 0x2500; a non-positive preferred size (ignored → default);
 * 1-, 2- and 3-page docs; a doc signed a SECOND time (two incremental
 * revisions, two signatures); plus a control with no preferred size set.
 *
 * Usage: java -cp <pdfbox-app.jar>:<bc>:<build> SignByteRangeFuzzProbe
 * Output: stdout, one key=value per line (UTF-8).
 */
public final class SignByteRangeFuzzProbe {

    private static final String SUBJECT_DN =
            "CN=oracle-sign-byterange-fuzz,O=pypdfbox-oracle,C=US";

    private static PrivateKey privateKey;
    private static X509Certificate certificate;

    public static void main(String[] args) throws Exception {
        Security.addProvider(new BouncyCastleProvider());
        PrintStream out = new PrintStream(System.out, true, "UTF-8");
        mintCert();

        int i = 0;
        // (label, pageCount, preferredSize<=0 means "don't call setter")
        i = emit(out, i, "default_1page", 1, 0);
        i = emit(out, i, "pref_4096_1page", 1, 4096);
        i = emit(out, i, "pref_12000_1page", 1, 12000);
        i = emit(out, i, "pref_0x2500_1page", 1, 0x2500);
        i = emit(out, i, "pref_nonpositive_1page", 1, -1);
        i = emit(out, i, "default_2page", 2, 0);
        i = emit(out, i, "default_3page", 3, 0);
        i = emit(out, i, "pref_8192_2page", 2, 8192);
        i = emit(out, i, "pref_3000_3page", 3, 3000);
        i = emit(out, i, "pref_20000_1page", 1, 20000);

        // Second-sign cases: sign once, then sign the already-signed bytes
        // again (a second incremental revision). Reports the SECOND save.
        i = emitSecondSign(out, i, "second_sign_1page", 1, 0, 0);
        i = emitSecondSign(out, i, "second_sign_pref", 1, 6000, 6000);
        i = emitSecondSign(out, i, "second_sign_2page", 2, 0, 0);

        // A few more sizes to widen the arithmetic coverage.
        i = emit(out, i, "pref_5000_1page", 1, 5000);
        i = emit(out, i, "pref_2500_1page", 1, 2500);
        i = emit(out, i, "pref_15000_2page", 2, 15000);
        i = emit(out, i, "default_4page", 4, 0);

        // A preferred size too small to hold the CMS blob: PDFBox throws
        // "Can't write signature, not enough space" at save time. Report the
        // raised state rather than aborting the whole probe.
        i = emitTooSmall(out, i, "pref_1024_too_small", 1, 1024);

        out.println("count=" + i);
    }

    private static int emit(PrintStream out, int idx, String label,
            int pageCount, int preferredSize) throws Exception {
        byte[] unsigned = buildPdf(pageCount);
        byte[] signed = sign(unsigned, preferredSize);
        report(out, idx, label, signed);
        return idx + 1;
    }

    private static int emitSecondSign(PrintStream out, int idx, String label,
            int pageCount, int pref1, int pref2) throws Exception {
        byte[] unsigned = buildPdf(pageCount);
        byte[] firstSigned = sign(unsigned, pref1);
        byte[] secondSigned = sign(firstSigned, pref2);
        report(out, idx, label, secondSigned);
        return idx + 1;
    }

    private static int emitTooSmall(PrintStream out, int idx, String label,
            int pageCount, int preferredSize) throws Exception {
        String prefix = "case." + idx + ".";
        out.println(prefix + "label=" + label);
        byte[] unsigned = buildPdf(pageCount);
        boolean raised = false;
        String message = "";
        try {
            sign(unsigned, preferredSize);
        } catch (Exception e) {
            raised = true;
            message = String.valueOf(e.getMessage());
        }
        out.println(prefix + "raised=" + raised);
        out.println(prefix + "messageHasNotEnoughSpace="
                + message.contains("not enough space"));
        return idx + 1;
    }

    private static void report(PrintStream out, int idx, String label,
            byte[] signed) throws Exception {
        String prefix = "case." + idx + ".";
        out.println(prefix + "label=" + label);

        File tmp = File.createTempFile("sbrf", ".pdf");
        tmp.deleteOnExit();
        Files.write(tmp.toPath(), signed);
        boolean loadable = false;
        try (PDDocument doc = Loader.loadPDF(tmp)) {
            loadable = true;
            List<PDSignature> sigs = doc.getSignatureDictionaries();
            out.println(prefix + "sigCount=" + sigs.size());
            // Report the LAST signature (the one just added this revision).
            PDSignature sig = sigs.get(sigs.size() - 1);
            int[] br = sig.getByteRange();
            int a = br[0], b = br[1], c = br[2], d = br[3];
            out.println(prefix + "byterange=" + a + "," + b + "," + c + "," + d);
            out.println(prefix + "fileLength=" + signed.length);

            int gap = c - (a + b);
            out.println(prefix + "gap=" + gap);

            // /Contents hex length: the bytes strictly between `<` and `>`.
            // The `<` sits at a+b (excluded convention), the `>` at c-1.
            int contentsHexLen = -1;
            if (a + b < signed.length && signed[a + b] == '<'
                    && c - 1 >= 0 && c - 1 < signed.length
                    && signed[c - 1] == '>') {
                contentsHexLen = (c - 1) - (a + b + 1);
            }
            out.println(prefix + "contentsHexLen=" + contentsHexLen);
            out.println(prefix + "gapEqualsHexPlusTwo="
                    + (gap == contentsHexLen + 2));

            boolean covers = (a == 0) && (c + d == signed.length);
            out.println(prefix + "coversWholeFileExceptContents=" + covers);
        }
        out.println(prefix + "loadable=" + loadable);
    }

    private static byte[] buildPdf(int pageCount) throws Exception {
        try (PDDocument doc = new PDDocument()) {
            for (int p = 0; p < pageCount; p++) {
                doc.addPage(new PDPage());
            }
            ByteArrayOutputStream bos = new ByteArrayOutputStream();
            doc.save(bos);
            return bos.toByteArray();
        }
    }

    private static byte[] sign(byte[] input, int preferredSize) throws Exception {
        SignatureInterface signer = new SignatureInterface() {
            @Override
            public byte[] sign(InputStream content) throws java.io.IOException {
                try {
                    byte[] data = content.readAllBytes();
                    CMSTypedData typed = new CMSProcessableByteArray(data);
                    CMSSignedDataGenerator gen = new CMSSignedDataGenerator();
                    ContentSigner sha256Signer =
                            new JcaContentSignerBuilder("SHA256withRSA")
                                    .setProvider(BouncyCastleProvider.PROVIDER_NAME)
                                    .build(privateKey);
                    gen.addSignerInfoGenerator(
                            new JcaSignerInfoGeneratorBuilder(
                                    new JcaDigestCalculatorProviderBuilder()
                                            .setProvider(BouncyCastleProvider.PROVIDER_NAME)
                                            .build())
                                    .build(sha256Signer, certificate));
                    gen.addCertificates(new JcaCertStore(
                            java.util.Collections.singletonList(certificate)));
                    CMSSignedData signed = gen.generate(typed, false);
                    return signed.getEncoded();
                } catch (Exception e) {
                    throw new java.io.IOException(e);
                }
            }
        };

        try (PDDocument doc = Loader.loadPDF(input)) {
            PDSignature signature = new PDSignature();
            signature.setFilter(PDSignature.FILTER_ADOBE_PPKLITE);
            signature.setSubFilter(PDSignature.SUBFILTER_ADBE_PKCS7_DETACHED);
            signature.setName("Oracle ByteRange Fuzz Probe");
            signature.setSignDate(Calendar.getInstance());

            ByteArrayOutputStream bos = new ByteArrayOutputStream();
            if (preferredSize > 0) {
                SignatureOptions options = new SignatureOptions();
                options.setPreferredSignatureSize(preferredSize);
                doc.addSignature(signature, signer, options);
            } else {
                doc.addSignature(signature, signer);
            }
            doc.saveIncremental(bos);
            return bos.toByteArray();
        }
    }

    private static void mintCert() throws Exception {
        KeyPairGenerator kpg = KeyPairGenerator.getInstance("RSA");
        kpg.initialize(2048);
        KeyPair kp = kpg.generateKeyPair();
        privateKey = kp.getPrivate();

        BigInteger serial = BigInteger.valueOf(System.currentTimeMillis());
        Calendar cal = Calendar.getInstance();
        Date notBefore = new Date(cal.getTimeInMillis() - 60_000L);
        cal.add(Calendar.DAY_OF_YEAR, 1);
        Date notAfter = cal.getTime();
        X500Name dn = new X500Name(SUBJECT_DN);

        JcaX509v3CertificateBuilder certBuilder = new JcaX509v3CertificateBuilder(
                dn, serial, notBefore, notAfter, dn, kp.getPublic());
        ContentSigner certSigner = new JcaContentSignerBuilder("SHA256withRSA")
                .setProvider(BouncyCastleProvider.PROVIDER_NAME)
                .build(privateKey);
        X509CertificateHolder holder = certBuilder.build(certSigner);
        certificate = new JcaX509CertificateConverter()
                .setProvider(BouncyCastleProvider.PROVIDER_NAME)
                .getCertificate(holder);
    }
}
