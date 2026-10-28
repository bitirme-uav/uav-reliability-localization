# BBM479 Project Proposal Report — metin kopyası

Kaynak: Drive `ProjectProposalTemplate.docx` (id 1NPsX0T42dgJW5kVJOW-DMAJnMo6_IG4S), Drive sürümü 2026-10-28
(danışmanın 28 Ekim dönütüne göre düzeltilmiş hali). Asıl belge: `BBM479_Proposal_Report.docx`.
Bu dosya ajanların okuyabilmesi için docx'ten çıkarılmış düz metindir: her satır bir paragraf ya da tablo hücresidir,
alt simgeler _{...} biçimindedir, şekiller yoktur. Şüphede docx esastır.

---

Hacettepe University
Computer Engineering Department
BBM479 Project Proposal Report
Project Details
Title
Calibrated Reliability-Aware RGB Map Relocalization for GPS/GNSS-Denied UAV Navigation
Short Description
(max. 200 words)
GPS/GNSS-denied Unmanned Aerial Vehicle (UAV) navigation requires a continuously updated local position estimate, which gradually accumulates drift, and occasional absolute map-based corrections to reduce this error. However, incorrect visual matches can produce unreliable geographic position estimates and potentially worsen navigation accuracy.
This project focuses on assessing the reliability of these absolute visual position fixes. Using real RGB UAV images, preloaded georeferenced satellite/aerial maps, and publicly available benchmark datasets, students will develop a UAV-to-map localization pipeline incorporating visual place recognition, feature matching, and geometric verification. A lightweight, calibrated reliability model will estimate the probability that each geographic fix is unsafe.
The central research question is whether calibrated reliability estimates can distinguish trustworthy from harmful geographic fixes more effectively than raw matching scores, a geometric quality gate, and conventional chi-square innovation gating and whether this improves sequential navigation. The proposed approach will be evaluated using a controlled drift simulator, including scenarios involving substantial accumulated drift and relocalization recovery. The pipeline will also be deployed on an NVIDIA Jetson Orin Nano to evaluate computational feasibility.
Expected outcomes include a reproducible localization framework, quantitative comparisons of reliability-aware correction policies, and an assessment of navigation robustness and embedded performance.
Supervisor
Dr. Öğr. Üyesi Selma Dilek
Technical and Scientific Difficulty
(    ) Easy        (    ) Mediocre     ( X ) Challenging
External Support
(    ) Yes                 ( X ) No
If yes,
Type
Details
(    ) Company Funding / Support
Company name:
Amount:
(    ) TÜBİTAK Project Fund
Type:
Amount:
(    ) Other Fund
Source :
Amount:
Group Members
Full Name
Student ID
1
Mehmed Akif Arslan
2230356003
2
Davut Şimşek
2230356050
3
Erdem Çankaya
2230356086
4
Alihan Ertekin
2220765038
Project Summary (           / 20 Points)
Explain the project in summary, including your motivation to do the project, your solution plan in short and your expected outcome and impact. You have to summarize your project between 200-500 words.
When Global Navigation Satellite System (GNSS) signals are unavailable or jammed, an unmanned aerial vehicle (UAV) must estimate its position with onboard sensors such as inertial units and visual odometry. These relative methods add a small error at every step, so the position estimate slowly drifts away from the truth. A common remedy is to compare the downward-looking camera image with georeferenced satellite or orthophoto maps stored onboard before the flight, and to use the match as an absolute position fix. Such fixes can remove the accumulated drift, but they are not always correct. Repetitive textures, seasonal changes, outdated maps and similar-looking places can produce a fix that looks convincing but is wrong. If the navigation filter accepts it, the estimate jumps to the wrong place and becomes worse than before.
Existing systems already compute map-based fixes and reject some bad ones. They use thresholds on inlier counts and reprojection error, hand-designed confidence weights, or the chi-square innovation test. It remains unclear whether confidence scores reflect actual error rates and reduce harmful corrections. This project therefore studies the trustworthiness of loosely coupled 2D metric fixes and their effect on navigation. It does not aim to build a new tightly coupled 6-Degrees of Freedom (DoF) navigation architecture. Our central question is whether calibrated image and matching evidence improves accept/reject decisions beyond a geometric gate inspired by Zhang et al. [4] and the standard chi-square innovation test.
We will use real UAV images from the public AerialVL benchmark [2] and a georeferenced map that is cut into tiles and stored locally. For each image, the pipeline retrieves similar tiles near the predicted position, matches local features, checks the geometry with Random Sample Consensus (RANSAC), and outputs either a 2D position fix or reports that no valid fix was found (NO_VALID_FIX). A lightweight model then estimates the probability that the fix is unsafe, that is, too far from the true position. The images are replayed in flight order through a deterministic 2D filter with simulated drift, so every policy faces exactly the same drift. All policies share the same recovery logic (NORMAL/REACQUIRE/LOST modes), which widens the search and inflates the position uncertainty after large drift. The main comparison counts harmful corrections per 100 localization attempts, with trajectory error as a guardrail. If feasible, AnyVisLoc [10] will serve as a complementary cross-domain check. Finally, the pipeline will be profiled on an NVIDIA Jetson Orin Nano for latency, memory and map storage.
The expected outcomes are a reproducible localization and evaluation pipeline, a fair comparison of correction policies under identical drift, calibration and trajectory findings, and measured resource costs on embedded hardware. The study will show whether, and under which drift and matching conditions, calibrated evidence adds value beyond existing geometric and statistical tests. The results may support or refute our hypotheses, and a negative or mixed result is still a useful finding. In either case, the work can help designers of GNSS-denied UAV navigation decide when a map-based correction should be trusted.
Problem Definition and Literature Review (           / 20 Points)
Define your problem as clearly as possible. Explain your inputs, your context, your outputs and your limitations. Try to use a scientific language as much as possible. Where necessary use citations to existing literature to create context and clarify the problem. Equations, flow charts, etc. are welcome.
Reliable navigation in GNSS-denied environments requires more than obtaining accurate visual position estimates: it also requires determining when those estimates can safely be used to correct accumulated navigation drift. This section formally defines the UAV-to-map localization and measurement-reliability problems, identifies the assumptions and limitations of the proposed system, and reviews existing approaches to visual geo-localization, confidence estimation, measurement validation, and navigation correction. Particular attention is given to the limitations of existing reliability measures and the research gap addressed by this project.
1. Problem Definition
This section defines the localization problem, its assumptions, and the reliability decisions studied.
1.1 Setting and the decision we study
A UAV flies over a known area after GNSS has become unavailable. Its onboard navigation keeps estimating the position by dead reckoning, and this estimate drifts with time and distance travelled [1], [2]. To correct the drift, the UAV occasionally compares a downward-looking camera image with georeferenced satellite or orthophoto tiles that were stored onboard before the flight, and computes an absolute 2D position fix from the match. No network link is used during the flight.
These fixes are not always correct. Feature-matching systems always have some probability of producing a false fix [3]. Seasonal and lighting changes, repetitive textures, local scene changes and map errors make UAV-to-map alignment unreliable, and wrong map observations make the estimated trajectory jump [4]. We therefore keep apart three things that are often treated as one: a successful image match, a correct geographic position, and a correction that actually improves the navigation estimate. An image can match an offset map perfectly, and an accurate fix can still worsen an estimate that was already better.
This project studies one decision: given a candidate fix and the evidence produced while computing it, should the navigation filter use it? The fix is treated as a loosely coupled 2D position measurement, as in SatLoc-Fusion [5]. Real UAV images from the AerialVL benchmark [2] are replayed in flight order, while drift and the filter are simulated so that every compared method faces exactly the same drift. Table 1 summarizes the information available during localization and distinguishes it from ground-truth information used only for training and evaluation.
Table 1. Information available at runtime and information used only for training and evaluation. A missing fix (NO_VALID_FIX) lowers availability; a wrong fix can corrupt the state.
Category
Item
Runtime inputs
Query image; preloaded map tiles with their georeferencing and descriptor index; camera intrinsics and altitude/attitude metadata where AerialVL provides them; predicted position and its uncertainty from the filter
Runtime outputs
Candidate tiles; a 2D position fix or NO_VALID_FIX; evidence from retrieval, matching and geometry; estimated probability that the fix is unsafe; accept/reject decision; corrected position
Training and evaluation only
Ground-truth position; true drift; fix error and unsafe label; whether the true position was inside the searched map area; whether the correction helped or harmed; trajectory error. None of these is used at runtime.
Figure 1. Problem overview (schematic). (a) A correct map fix removes the accumulated drift. (b) A fix matched to a look-alike area has many inliers and a small reprojection error, but accepting it moves the estimate away from the true position.
1.2 How the camera sees the ground
Photogrammetry describes image formation with the collinearity condition: once lens distortion has been removed, the ray from a ground point passes in a straight line through the lens centre to the image [6]. With all positions expressed in one metric map frame (e.g., Universal Transverse Mercator (UTM)), a ground point (E, N, U) is imaged at pixel (u, v) by [7], [8]:
s·[u, v, 1]ᵀ = K [R | t] [E, N, U, 1]ᵀ     (1)
where K is the camera intrinsic matrix (focal lengths and principal point), R and t transform map coordinates into the camera frame, and s is the projective scale (camera-frame depth). Here, E,N,U denote easting, northing and height, and u,v are undistorted pixel coordinates. Wang et al. use the same relation in its photogrammetric collinearity form [9]. Read backwards, each pixel defines a ray from the camera, and the ground point it shows is where that ray meets the terrain.
Figure 2. Imaging geometry. (a) A nadir camera at height H covers a ground footprint; one pixel covers GSD = H·p/f on the ground. (b) In a perspective UAV image, elevated points are displaced away from the image centre, whereas an orthophoto projects every point straight down. (c) A 5° tilt at 150 m shifts the ground point under the image centre by about 13 m (tilt exaggerated).
Two consequences follow. First, the ground size of one pixel (ground sample distance, GSD) depends on the altitude: for a vertical image over flat ground, the image scale is f/H, where H is the height above ground [6]. Second, the UAV image and the map tiles are geometrically different. An orthophoto is corrected with a terrain model so that every point appears as if seen from directly above [6], whereas the UAV image is a perspective view in which tall objects lean away from the image centre. For approximately planar terrain, Eq. (1) induces a 3×3 homography between the UAV image and the map [7], [10]. For non-planar terrain, especially under oblique viewing, 3D geometry may be needed, such as surface-aware projection or pose estimation from 2D–3D correspondences using Perspective-n-Point (PnP) [9], [10]. AerialVL was flown at 120–200 m with a gimbal-stabilized downward camera [2], so we start from the planar model and will check it along each route.
1.3 From a query image to a metric fix
Absolute visual localization is usually done in three steps [7].
Retrieval. A global descriptor of the query image is compared with those of the map tiles, and the most similar tiles are returned [2], [1], [5]. We search only the tiles near the predicted position, within a radius that grows with the filter's uncertainty, since the search range is set by the position uncertainty [7]. This saves computation, as in sequence matching [11], but it depends on the prediction. If the filter underestimates its error, the correct tile is never searched, and a recovery mode (REACQUIRE) must widen the search within the same onboard map and inflate the position uncertainty, so that the χ² test can accept a correct but distant fix. Retrieval gives a place, not a metric position [2].
Local matching. Keypoints are detected in the query and in each candidate tile. Each query keypoint is paired with the tile keypoint whose descriptor is most similar, and the pair is kept only if this choice is confident. SuperPoint features with the LightGlue matcher are a common choice [1], [9], [12].
Geometric verification. Some of these matches are still wrong. RANSAC repeatedly fits the image-to-map transformation to small random subsets of matches and keeps the transformation that most matches agree with; these matches are the inliers [13], [5], [10]. A match is an inlier if its reprojection error, defined in (2), is below a pixel tolerance (5 px in OrthoLoC [8]).
If there are too few inliers or the transformation is degenerate, the attempt returns NO_VALID_FIX. Otherwise, the image centre is mapped through the transformation into map coordinates, and this point is the fix. This assumes the camera looks straight down, as SatLoc-Fusion does [5]; a 5° tilt at 150 m already shifts the fix by about 13 m. Neither the best tile centre nor a good homography fit is by itself a correct UAV position.
Figure 3. Example of map-based localization. Top: satellite tile (left) with the UAV image centre projected as the position fix (green dot), and the UAV image (right). Bottom: local feature matches between the two images. Reproduced from [5] (CC BY 4.0).
1.4 Reprojection error versus fix reliability
Reprojection takes a matched map point, projects it back into the query image with the estimated geometry, and measures how far it lands from the pixel where the matcher found it
eᵢ = ‖uᵢ − ûᵢ‖ ,   ē = (1/|ℐ|) Σᵢ∈ℐ eᵢ     (2)
Here, eᵢ is the reprojection error, uᵢ is the matched pixel, ûᵢ is the reprojected pixel, ℐ is the inlier set, and ē is the mean reprojection error in pixels. Besides deciding which matches are inliers, ē is widely used as a quality signal. It is one of the gating criteria of Zhang et al. [4], a re-localization trigger in OrthoTrack [14], and the acceptance test of OrthoLoC's refinement step [8].
A small ē does not prove that a fix is correct:
It measures consistency, not correctness. The inliers were selected because their error was small, so a small mean is partly guaranteed by construction.
A wrong place can look consistent. Repetitive patterns such as crop rows, road grids or similar roofs let many matches agree on a wrong tile [13], [8], [12].
Figure 4. Typical failure cases of map-based localization: (a) all top-5 retrieved map tiles are visually similar to the UAV image but geographically wrong (ground truth in green); (b) low-altitude oblique views make image-to-map matching harder; (c) temporal and source differences between the UAV image and the satellite map. Reproduced from [10].
A small error does not mean a well-constrained pose. OrthoTrack found that a fixed reprojection threshold did not help, "since the reprojection error alone does not sufficiently reflect the quality of the estimated pose" [14].
Map errors are invisible to it. ē measures agreement with the map, not with the world. An orthophoto inherits errors from its terrain model and ground control [6], and GeoVINS attributes part of its remaining error to georeferencing errors in the orthoimagery [1]. In AnyVisLoc, switching from aerial maps to satellite maps with a coarse 30 m surface model lowered accuracy within 5 m from 74.1% to 18.5% [10].
It is not a probability. A value of 1.5 px does not say how often such fixes are wrong.
We therefore use ē as one input among others, not as the decision itself (see Table 2).
Table 2. Mean reprojection error versus the proposed reliability output.
Mean reprojection error ēₜ
Calibrated unsafe-fix probability q̂ₜ
Question
Do the selected matches agree with the estimated transformation?
How likely is it that this fix is more than T metres from the true position?
Unit
Pixels
Probability of a metric failure
Computed from
Inliers chosen by the same estimator
Several signals: ē, inlier count and spread, retrieval similarity and margin, spread of the candidate tiles, scale consistency with altitude
Link to ground truth
None
Fitted on training sequences, checked on held-out sequences
Role
RANSAC tolerance; one criterion of a heuristic gate [4]
Accept/reject decision at an operating point chosen on validation data
For evaluation, a valid fix z is labelled unsafe if it is farther than T metres from the ground-truth position p*:
y = 1[‖z − p*‖ > T] ,   q̂ = f(x) ≈ P(y = 1 | x)     (3)
Here, y is the binary ground-truth label indicating whether a candidate position fix is unsafe, x is the evidence vector, and f is a lightweight model. T is provisionally 25 m and will be fixed before any test sequence is processed. We call q̂ calibrated if, among fixes that receive q̂ ≈ 0.2, about 20% are actually unsafe; only then can a threshold on q̂ be read as an expected error rate. q̂ is a probability of failure, not a position covariance, so it does not replace the measurement noise of the filter. NO_VALID_FIX attempts receive no label and are counted only for availability. We will compare an image/matching-only feature set with a prior-aware set that also uses the distance to the predicted position; even the image-only features depend on the prior, because retrieval searches only near it.
1.5 Using a fix and the research question
The filter compares each valid fix z with its predicted position p-. The resulting innovation ν is normalized by its covariance S, where P- is the predicted position covariance and R_{nominal} is the assumed covariance of the map-based fix:
ν = z − p̂⁻,     S = P⁻ + Rₙₒₘᵢₙₐₗ,     d² = νᵀ S⁻¹ ν     (4)
Figure 5. χ² innovation gating (illustrative). (a) With a correct prior, the 95% gate (d² ≤ 5.99) accepts a correct fix and rejects a distant wrong fix. (b) After large drift, the same gate rejects the correct fix and accepts a wrong fix that happens to lie near the drifted estimate.
Under Gaussian errors and correctly specified covariance, d2 follows a chi-square (χ²) distribution with two degrees of freedom, and the fix is rejected when d² > 5.99 (95% level) [15], [3]. Groves [3] describes this innovation filtering as a common way to remove false fixes from feature-matching systems. Groves also notes that it depends on correct noise assumptionsand responds poorly to errors that build up gradually [3]. In our setting this means that after large drift the test can reject correct fixes, while a run of mutually consistent wrong fixes can pass it. To make the filter receptive again, Groves [3] recommends increasing the state uncertainty [3], which our REACQUIRE mode follows.
Even an accurate fix can worsen the navigation estimate. We therefore measure the change in position error Δe caused by each accepted correction:
Δe = ‖p̂⁺ − p*‖₂ − ‖p̂⁻ − p*‖₂     (5)
Here, p- and p+ are the position estimates immediately before and after correction, respectively, and p* is the ground-truth position. An applied correction is considered harmful when Δe>5 m. We report harmful corrections per 100 scheduled localization attempts, including attempts returning NO_VALID_FIX. This 5 m tolerance is distinct from the unsafe-fix threshold T. Rejected or missing fixes do not update the state.
The main research question is: does a calibrated risk score followed by the χ² test reduce harmful corrections compared with a gate inspired by Zhang et al. [4] followed by the same test, when both accept a similar share of fixes on validation data and use the same filter noise and recovery logic, without increasing the absolute trajectory error (ATE)?
2. Literature Review
This section reviews relevant localization methods, benchmarks, and reliability mechanisms to identify the research gap.
2.1 Absolute visual localization pipelines and benchmarks
A 2026 survey describes absolute visual localization of UAVs as a chain of retrieval, pixel-level matching and pose estimation. It notes that the planar model of high-altitude nadir imaging fails at low altitude, and reports that the fastest single-frame methods on edge platforms usually still need more than 0.3 s [7].
AerialVL [2] provides eleven real sequences (about 70 km) over roughly 20 km², flown at 120–200 m in daytime and at nightfall, with GNSS ground truth and a Google Earth reference map. Its benchmark shows visual-inertial odometry (VIO) drift growing with distance and visual alignment failing over farmland and at turning points. Its modular framework succeeds (error below 25 m) on 79.6–88.0% of three trajectories. The framework branches on whether a frame was "correctly matched", but no confidence for that decision is modelled or evaluated.
AnyVisLoc [10] extends the problem to low-altitude, oblique views with about 18,000 images. Its best pipeline re-ranks candidates by inlier count and localizes 74.1% of images within 5 m with aerial maps.
Wang et al. [9] match UAV images to a satellite true orthophoto and digital surface model (DSM) with SuperPoint and LightGlue and estimate the pose by spatial resection. They find that success depends strongly on terrain texture, flight altitude and tile size, and they add a reliability-oriented verification step because GNSS-denied operation gives no online accuracy feedback.
Bi et al. [12] introduce XIAN-Visloc, more than 80 km of continuous real flights, and show that tile-library design and repetitive buildings and roads make large-area retrieval difficult. Its timestamps, ground truth, georeferencing and licence will be checked before it is considered as a complement to AerialVL.
OrthoLoC [8] estimates 6-DoF poses against public orthophotos and DSMs and accepts its refinement only when the reprojection error decreases.
2.2 How map fixes are used in navigation
Existing systems already detect and handle bad map observations, each in its own way.
GeoVINS [1] fuses orthoimagery- and DSM-derived measurements with inertial and visual measurements in a tightly coupled Kalman filter. It re-runs place recognition after prolonged matching failure.
SatLoc-Fusion [5] computes a hand-designed confidence from the retrieval-score margin and the UAV-to-satellite GSD ratio and uses it to inflate the measurement variance in a 2D Kalman filter. The authors leave a sensitivity analysis of this mapping to future work.
Zhang et al. [4] periodically align the UAV image with an orthophoto patch cropped around the visual odometry (VO) predicted position. They gate the result on the number of matches, RANSAC inliers, inlier ratio, mean reprojection error and the correction displacement, and use a local relocalization module when tracking degrades.
OrthoTrack [14] triggers re-localization from point count, spatial spread and an adaptive reprojection threshold.
Sequence matching [11] matches each frame only against a few reference patches along the trajectory. Like our prior-centred search, this saves computation but depends on the previous position being right.
Abdelkader et al. [16] use learning in a different place. Their models correct the residuals of a terrain-aided extended Kalman filter (EKF), which improves the estimator rather than deciding whether a given map fix should be used.
These mechanisms are thresholds or weights on raw signals. In the works reviewed here we found no test of whether a confidence score or gate matches an observed error rate, and no comparison of such a gate with the χ² innovation test under identical drift. The gate of Zhang et al. [4] is the closest to our baseline and shows why this matters. Its displacement criterion is a raw distance to the prediction, so after large drift it rejects correct but distant fixes, and its reprojection criterion has the limits listed in Section 1.4. Our Zhang-inspired baseline is an adaptation, not a reproduction.
2.3 Uncertainty and integrity
Zaffar et al. [13] compared uncertainty estimates for visual place recognition and proposed spatial uncertainty estimation (SUE). SUE weights the map positions of the top retrieved references by descriptor distance and uses their spread as the uncertainty, so a scattered candidate set signals perceptual aliasing. SUE complemented geometric verification, but it is a ranking score evaluated on ground-level datasets and describes the retrieved place rather than a metric fix; we consider it as an optional retrieval-level baseline and feature.
The classical statistical tool is the χ² test on the normalized innovation [15]. Groves places it within a hierarchy of integrity monitoring, from fault detection to certified integrity, and stresses that its thresholds rest on covariance assumptions that should be checked in practice [3].
2.4 Research gap and research questions (RQ)
The reviewed work provides:
pipelines that produce fixes [2], [10], [9];
navigation systems with failure handling [1], [4];
heuristic confidence weighting [5];
retrieval uncertainty [13];
innovation gating [15], [3].
It does not show whether the evidence produced while computing a map fix can be turned into a calibrated probability of failure. Nor does it show whether such a probability improves accept/reject decisions beyond a geometric gate and the χ² test under the same drift. The project addresses the following RQs:
RQ1 – Failure discrimination. How well do retrieval, matching and geometric signals, alone and combined, separate unsafe from safe fixes?
RQ2 – Calibration and transfer. Can a lightweight model give calibrated unsafe-fix probabilities on held-out AerialVL sequences, and how much does calibration degrade on AnyVisLoc?
RQ3 – Sequential correction. At similar acceptance rates, does calibrated risk followed by the χ² test reduce harmful corrections compared with the Zhang-inspired gate, without increasing trajectory error?
RQ4 – Severe-drift recovery. When the prediction is badly wrong, can REACQUIRE accept a correct distant fix while rejecting isolated and persistent wrong fixes?
RQ5 – Jetson feasibility. What latency, memory and map-storage costs does the pipeline incur on an NVIDIA Jetson Orin Nano?
References
[1] C. Li et al., "GeoVINS: Geographic-visual-inertial navigation system for large-scale drift-free aerial state estimation," IEEE Trans. Robot., vol. 41, pp. 5835–5853, 2025, doi: 10.1109/TRO.2025.3613467.
[2] M. He et al., "AerialVL: A dataset, baseline and algorithm framework for aerial-based visual localization with reference map," IEEE Robot. Autom. Lett., vol. 9, no. 10, pp. 8210–8217, Oct. 2024, doi: 10.1109/LRA.2024.3441491.
[3] P. D. Groves, "Fault detection and integrity monitoring," in Principles of GNSS, Inertial, and Multisensor Integrated Navigation Systems. Boston, MA, USA: Artech House, 2008, ch. 15, pp. 451–470.
[4] Y. Zhang, Q. Yi, Y. Zong, Z. Yan, and H. He, "Map-aided UAV visual localization via visual odometry and orthophoto map alignment," in Proc. 2nd Int. Conf. Unmanned Syst. Technol. (UST), 2026, pp. 72–78, doi: 10.1109/UST70584.2026.11663724.
[5] X. Zhou, X. Zhang, X. Yang, J. Zhao, Z. Liu, and F. Shuang, "Towards UAV localization in GNSS-denied environments: The SatLoc dataset and a hierarchical adaptive fusion framework," Remote Sens., vol. 17, no. 17, Art. no. 3048, 2025, doi: 10.3390/rs17173048.
[6] M. J. Starek and B. E. Wilkinson, "Aerial surveying technology," in Surveying and Geomatics Engineering. Reston, VA, USA: American Society of Civil Engineers, 2022, ch. 10, pp. 341–392, doi: 10.1061/9780784416037.ch10.
[7] Y. Ye et al., "Survey on absolute visual localization techniques for low-altitude unmanned aerial vehicles," J. Nat. Univ. Defense Technol., vol. 48, no. 2, pp. 29–47, Apr. 2026, doi: 10.11887/j.issn.1001-2486.25120033 (in Chinese).
[8] O. Dhaouadi, R. Marin, J. Meier, J. Kaiser, and D. Cremers, "OrthoLoC: UAV 6-DoF localization and calibration using orthographic geodata," in Proc. Adv. Neural Inf. Process. Syst. (NeurIPS), 2025, arXiv:2509.18350.
[9] T.-C. Wang, L.-H. Tsou, J.-P. Jhan, and R.-S. Tang, "UAV visual localization in GNSS-denied environments," Int. Arch. Photogramm. Remote Sens. Spatial Inf. Sci., vol. XLIX-B1-2026, pp. 55–61, 2026, doi: 10.5194/isprs-archives-XLIX-B1-2026-55-2026.
[10] Y. Ye et al., "Exploring the best way for UAV visual localization under low-altitude multi-view observation condition: A benchmark," in Proc. IEEE/CVF Conf. Comput. Vis. Pattern Recognit. Findings (CVPRF), 2026, pp. 1731–1741, doi: 10.1109/CVPRF71909.2026.00171.
[11] Z. Wang et al., "Sequence matching for image-based UAV-to-satellite geolocalization," IEEE Trans. Geosci. Remote Sens., vol. 62, pp. 1–15, 2024, doi: 10.1109/TGRS.2024.3359605.
[12] C. Bi et al., "UAV coarse visual localization in large-scale continuous scenes," ISPRS J. Photogramm. Remote Sens., vol. 238, pp. 243–260, 2026, doi: 10.1016/j.isprsjprs.2026.04.054.
[13] M. Zaffar, L. Nan, and J. F. P. Kooij, "On the estimation of image-matching uncertainty in visual place recognition," in Proc. IEEE/CVF Conf. Comput. Vis. Pattern Recognit. (CVPR), 2024, pp. 17743–17753, doi: 10.1109/CVPR52733.2024.01680.
[14] O. Dhaouadi, Z. Bauer, J. M. Meier, O. Wysocki, M. Pollefeys, and D. Cremers, "OrthoTrack: Continuous 6-DoF UAV trajectory estimation anchored in public orthophotos," in Proc. Eur. Conf. Comput. Vis. (ECCV), 2026, arXiv:2606.25245.
[15] Y. Bar-Shalom, X. R. Li, and T. Kirubarajan, Estimation with Applications to Tracking and Navigation. New York, NY, USA: Wiley, 2001, doi: 10.1002/0471221279.
[16] M. Abdelkader et al., "A two-stage residual extended Kalman filter using extreme gradient boosting and Kolmogorov–Arnold networks for terrain-aided unmanned aerial vehicle localization in global navigation satellite system-denied environments," Eng. Appl. Artif. Intell., vol. 173, Art. no. 114430, 2026, doi: 10.1016/j.engappai.2026.114430.
Solution Plan (            / 20 Points)
Explain the potential paths to solution. You should propose at least one solid plan to attack the problem. Dissect your plan into steps and clearly identify the inputs and outputs of each step. You are not expected to provide the technical details of each step. Provide a weekly timeline/Gantt chart displaying the relevant weeks for each step.
We will build the project in seven steps over 28 weeks (see Figure 6). Each step uses the outputs of the previous steps and ends with a milestone that can be checked. The main goal is to develop a reliability model for UAV-to-map localization and compare its performance with existing geometric and statistical methods.
The project will first establish a working localization pipeline using real UAV images and preloaded georeferenced maps. Different feature extraction and matching methods will be tested before selecting the localization frontend. We will then train a lightweight reliability classifier and compare it with conventional methods under the same experimental conditions. The final stages will focus on recovery, held-out evaluation and embedded performance. The plan leaves room for changes based on validation results, particularly in the selection of feature extraction methods and the reliability model. The main evaluation protocol will be fixed before testing.
Step 1 – Data audit, map preparation and split (Weeks 1–4)
Input: AerialVL image sequences, GNSS ground truth, the reference map and related papers.
Check the coordinate systems of the images, ground truth and reference map, and convert their positions into a common metric coordinate system.
Prepare overlapping georeferenced map tiles and build an offline retrieval index. Tile size and overlap will be selected by considering camera field of view, altitude and map resolution.
Examine alternative map representations, such as geographically indexed reference features, if fixed tile sizes are not suitable for different viewing conditions.
Check the frame order, timestamps and available metadata. Divide the eleven AerialVL sequences into four training, two validation and five test sequences using altitude, lighting and route information.
Produce an initial geographic position estimate for a single UAV image to verify the map preparation and localization procedure.
Output: Verified dataset, georeferenced map index, fixed sequence-level split and an initial localization demonstration (Milestone M1).
Step 2 – Visual localization and feature-matching experiments (Weeks 5–8)
Input: UAV query images, the georeferenced map index, simulated position priors and ground-truth positions.
Build the localization pipeline using visual place recognition, local feature extraction, feature matching and geometric verification.
Experiment with classical and learning-based feature extraction methods, including ORB, SIFT, XFeat and SuperPoint, using compatible matching algorithms.
Compare the methods using matching success, geometric consistency, localization accuracy and computational cost. Select the frontend configuration using training and validation results.
Retrieve candidate map regions within a prior-centred search window, verify local correspondences with RANSAC and convert valid transformations into metric geographic positions.
Run the selected localization pipeline under predefined prior offsets and search radii, and save the resulting geographic measurements together with their matching and geometric quality indicators.
Examine the distribution of localization errors on training data to determine the unsafe-fix threshold used for reliability modelling.
Output: Working localization pipeline, feature-matching comparison results, candidate-fix records and a defined training-label rule (Milestone M2).
Step 3 – Reliability model and comparison methods (Weeks 9–12)
Input: Training and validation localization records, matching statistics and geographic position errors.
Train lightweight classification models to estimate the probability that a geographic position measurement is unsafe. Candidate algorithms will include Logistic Regression, Random Forest and Gradient-Boosted Decision Trees.
Use matching and geometric quality indicators as model inputs, including reprojection error, inlier statistics, correspondence distribution and retrieval scores.
Implement the comparison methods: reprojection-error thresholding, Zhang-inspired geometric gating and chi-square innovation gating. Raw matching scores and SUE are optional additional comparators.
Compare candidate classifiers and tune their parameters using training and validation data. Evaluate probability calibration using Platt Scaling or Isotonic Regression where appropriate.
Discuss metric error regression and probabilistic error estimation as possible alternative model formulations.
Begin preparing the localization frontend and selected reliability model for the Jetson Orin Nano.
Output: Trained reliability classifier, implemented comparison methods, initial calibration results and a preliminary Jetson implementation (Milestone M3).
Step 4 – Controlled evaluation and primary experiment E0 (Weeks 13–16)
Input: Ordered validation sequences, candidate geographic measurements, matching statistics, simulated navigation priors and ground truth.
Build a deterministic evaluation framework that replays the recorded UAV images and uses predefined position-drift conditions.
Implement the primary experiment E0, a closed-loop sequential replay that compares the proposed policy (calibrated risk followed by the chi-square test) with the Zhang-inspired gate followed by the same test. The calibrated model without the chi-square test, reprojection-error thresholding, the Zhang-inspired gate and chi-square gating are also run as standalone policies.
In the fixed-candidate evaluation, score all methods on the same candidate records. In E0, give every policy the same images, drift realizations, localization frontend, filter noise and recovery rules.
Select decision thresholds on validation data and compare methods at similar accepted-fix coverage where applicable.
Measure harmful corrections per 100 scheduled localization attempts as the primary E0 metric, with absolute trajectory error (ATE) as a guardrail. Measure failure discrimination, unsafe-fix acceptance, safe-fix retention and calibration in the fixed-candidate evaluation.
Output: Reproducible E0 experiment runner, comparative validation results and validation-selected thresholds (Milestone M4).
Step 5 – Recovery, stress tests and configuration freeze (Weeks 17–20)
Input: The experiment runner, selected reliability methods and challenging localization scenarios.
Implement a shared NORMAL / REACQUIRE / LOST mechanism, including covariance inflation and a multi-fix confirmation rule, to handle prolonged localization failures and substantial accumulated drift.
Test three cases: a correct but distant geographic fix, an isolated incorrect fix and repeated incorrect fixes that appear geometrically consistent.
Evaluate the ability of the reliability methods to identify valid measurements during difficult localization and recovery conditions.
Profile the localization and reliability pipeline on the Jetson Orin Nano, including latency, memory usage and map storage.
Freeze the selected frontend, model parameters, baseline thresholds and experimental configuration before accessing the test sequences.
Output: Recovery and robustness results, preliminary Jetson measurements and frozen configuration (Milestone M5).
Step 6 – Final test and additional experiments (Weeks 21–24)
Input: Frozen configuration, five held-out test sequences and available supplementary datasets.
Run the primary E0 experiment on the test sequences using the fixed experimental protocol.
Compare the reliability classifier with the geometric and statistical methods using common evaluation metrics.
Report harmful corrections per 100 scheduled attempts and ATE for E0, and classification performance, unsafe-fix acceptance, risk–coverage behaviour and calibration for the fixed-candidate evaluation.
Analyze performance under substantial drift and challenging visual matching conditions.
If time and data availability allow, evaluate cross-dataset generalization using AnyVisLoc and examine the effects of alternative feature extraction configurations.
Output: Final comparison tables, reliability plots, robustness results and supplementary analyses (Milestone M6).
Step 7 – Reporting and demonstration (Weeks 25–28)
Input: Final experimental results, trained models, source code, configuration files and evaluation logs.
Write the final report and document the localization framework, reliability model, baseline methods and evaluation protocol.
Prepare a demonstration showing the UAV image, retrieved map region, geographic position estimate and reliability decision.
Package the source code, experiment configurations, random seeds and evaluation scripts to support reproducibility.
Discuss the conditions under which the proposed reliability model performs better or worse than the comparison methods.
Output: Final report, demonstration and reproducible software package (Milestone M7).
Weekly timeline
Figure 6. Planned 28-week development timeline (Gantt chart). Each four-week period ends with a milestone (M1–M7); Jetson preparation runs alongside Steps 3 and 5. Week numbers will be matched to the official semester dates.
Fallback paths
Some steps depend on dataset properties, algorithm performance or hardware compatibility that have not yet been fully verified. Table 3 describes the alternatives that will be used if these steps encounter difficulties.
Table 3. Fallback paths and their effects.
Area
Trigger
Fallback and effect
Dataset
AerialVL does not provide suitable ordered frames or ground truth for sequential evaluation.
Use UAV-VisLoc or another dataset with the necessary sequence and position information. Results will not be directly comparable with AerialVL experiments.
Feature extraction
A selected extractor produces too few reliable matches or excessive computation time.
Compare alternative ORB, SIFT, XFeat or other suitable configurations on validation data and select a feasible frontend before the final freeze.
Map representation
Fixed tiles are unsuitable for changing altitude, field of view or image scale.
Adjust tile overlap and size or use geographically indexed reference features.
Candidate generation
The full candidate-record cache requires excessive time or storage.
Use a predefined grid of prior offsets and search radii with a reproducible subset of localization attempts.
Reliability model
More complex classifiers do not improve validation results.
Retain the best validated classifier, including Logistic Regression if it provides comparable performance. Negative findings will be reported.
Deployment
TensorRT conversion fails or the selected configuration exceeds available resources.
Use ONNX Runtime or PyTorch and reduce frontend computational cost where possible.
Cross-dataset transfer
AnyVisLoc cannot be processed reliably because of data access or viewpoint differences.
Restrict the main evaluation to AerialVL and report transfer evaluation as an unavailable extension.
Methodology (               / 20 Points)
Explain the methodology you will use in each of the steps you have described under your solution plan. Here, you are expected to give more technical details about each solution step. Also explain how each member of the project will contribute by assigning members to steps. If you are assigning more than one member to a step, explain their specific role and how the work will be divided among them.
This section explains how the steps of the Solution Plan will be implemented and evaluated. Figure 7 shows the planned localization and reliability assessment pipeline. The framework will use real UAV images and georeferenced maps to generate geographic position measurements. A learned reliability model and several conventional methods will then assess the quality of these measurements.
Ground truth will be used to produce training labels and calculate evaluation metrics. It will not be available to the reliability methods during inference. The experimental parameters below are planned starting values and will be finalized using training and validation data before the test evaluation.
Figure 7. Proposed UAV-to-map localization pipeline, illustrating offline map preparation, onboard localization and reliability-aware decision-making, and the separation of runtime processing from training and evaluation.
1. Data and leakage prevention
AerialVL will be our main benchmark because it provides real, ordered UAV image sequences with GNSS ground truth and a reference map. We will divide the eleven sequences into four training, two validation and five test sequences based on metadata such as altitude, time of day and route characteristics. A sequence will not be divided between different sets because consecutive frames contain highly similar visual information. We will also examine spatial overlap between the sequences and report its effect on generalization. The test sequences will remain unused until the configuration freeze in Month 5.
All geographic positions, including the map coordinates, predicted positions, candidate fixes and ground truth, will be converted into a common metric coordinate system, such as UTM.
Ground truth will only be used to generate training targets, create controlled simulation conditions and calculate evaluation metrics. True position errors and simulated drift offsets will not be provided as runtime reliability features. AnyVisLoc will be considered separately for cross-dataset transfer evaluation, since its data structure and viewing conditions differ from the sequential AerialVL experiments.
Figure 8. AerialVL reference satellite patches (top row) and UAV frames from the image sequences (bottom rows), covering nightfall, different flight heights and different scene types. Reproduced from [2].
2. Map preparation and localization
The reference map will be divided into overlapping georeferenced tiles. A global image descriptor from a published visual place recognition model will be computed for each tile, and the descriptors will be stored in an offline retrieval index. Tile size and overlap will be selected by considering camera field of view, altitude and map resolution. As an alternative, reference features may be stored together with their geographic coordinates so that the relevant map regions can be selected more flexibly when camera footprint or image scale changes. At each localization attempt, the UAV image will be compared with reference regions around the predicted position. The search radius will be controlled by the experimental configuration. We will initially examine search radii between 60 m and 400 m, with larger regions used for recovery experiments. When heading information is available, the query image may be rotated to a common orientation before retrieval.
For the top-K retrieved regions, local features will be extracted and matched. We will compare classical and learning-based approaches, including ORB, SIFT, XFeat and SuperPoint, using compatible matching algorithms. The comparison will consider matching success, geometric consistency, geographic localization error and processing time. After selecting the frontend, RANSAC will estimate the image-to-map transformation from the matched correspondences. For approximately nadir images over locally planar terrain, a homography will provide the initial geometric model. A transformation will be considered valid when it has sufficient inlier support and does not show obvious geometric degeneracy. We will check the number and distribution of inliers, reprojection error and the plausibility of the estimated transformation. The image centre will then be transformed into map coordinates to obtain the candidate geographic fix:
z_{t}=E_{t},N_{t}T
where E_{t} and N_{t} are the estimated east and north coordinates in metres.
This initial 2D formulation assumes that the camera is approximately downward-looking. Camera orientation, altitude and available calibration information will be used to check this assumption. Camera-to-UAV offsets will be accounted for when the necessary metadata is available. If no valid geometric transformation can be obtained, the attempt will return NO_VALID_FIX. Attempts outside the reference-map coverage and attempts in which the correct region is excluded from the search window will be recorded separately. The same localization frontend and configuration will be used for every method. In the fixed-candidate evaluation all methods score identical candidate fixes; in the closed-loop evaluation the candidates may differ between methods (Section 5).
3. Fix records and training targets
Figure 9.Methodology and experimental workflow, covering dataset preparation, candidate position fix generation, unsafe-fix labeling, reliability model training, probability calibration, and evaluation.
To train the reliability model, we need localization examples with different levels of geographic error. We will generate these examples by running the localization pipeline under predefined search conditions and simulated position offsets. The initial prior-offset conditions will include 0, 30, 80, 200 and 300 metres. Different search radii and offset directions will be used to generate both accurate and incorrect candidate measurements. The conditions will be generated reproducibly using fixed random seeds. Every localization attempt will be stored as a record containing its input conditions, matching information and localization result. For valid fixes, the runtime feature vector will include the available matching and geometric quality indicators:
- Number of feature matches and RANSAC inliers.
- Inlier ratio and mean reprojection error.
- Spatial distribution of matched features.
- Geometric transformation consistency.
- Retrieval similarity and the difference between the top retrieved candidates.
- Distance and Mahalanobis distance d² between the candidate fix and the predicted position (prior-aware feature set only).
Additional features, including image descriptors or feature-level representations from the query and reference images, may be investigated if they provide useful information.
The actual geographic error of a valid fix will be calculated as:
e_{fix,t}=‖z_{t}−p_{t}*‖_{2}
where p_{t}* is the ground-truth 2D position.
For the initial binary classification task, the training label will be:
y_{t}=𝟏e_{fix,t}>T
where y_{t}=1 indicates an unsafe fix and T is the selected error threshold.
T is provisionally 25 m, the success criterion of AerialVL [2]. The final value will be chosen from the training sequences only, before any validation-based tuning. Fixes whose retrieved region contains the true position usually form a cluster of small errors, while fixes from a wrong region lie much farther away. T will be placed just above this cluster: it is the smallest value in {10, 15, 25, 50} m that exceeds the 95th percentile of the errors of such training fixes. T is then frozen and used unchanged for validation and test. The neighbouring values will be reported on validation data as a sensitivity analysis.
Only valid geographic fixes will receive a binary safety label. NO_VALID_FIX attempts will remain in the records for availability analysis. Training samples will be balanced or weighted at the sequence and query levels to prevent long sequences and repeated prior-offset conditions from dominating the model.
4. Reliability model and comparison methods
This section presents the proposed reliability model and the baseline methods used for comparison.
Figure 10. Proposed calibrated reliability estimation framework, showing runtime feature extraction, classification, probability calibration, and comparison with conventional geometric and statistical gating methods.
4.1. Proposed reliability classifier
The reliability model will be a lightweight supervised classifier trained on the visual matching and geometric quality features obtained from the localization pipeline. We will evaluate three candidate algorithms.
Logistic Regression will provide a simple linear classification baseline. Its input features will be standardized, and L2 regularization will be used to reduce overfitting.
Random Forest will be used to model nonlinear relationships between different reliability indicators. The number of trees, maximum tree depth and minimum leaf size will be selected using validation results.
Gradient-Boosted Decision Trees (XGBoost) will be used as a more flexible tree-based model. Parameters such as tree depth, learning rate and number of boosting rounds will be tuned to balance performance and model complexity.
All three algorithms will use the same training records and available runtime features. Logistic Regression and gradient boosting will use binary classification objectives, while Random Forest will use its standard tree-splitting criterion. Class weighting will be considered if unsafe fixes are substantially less common than safe fixes. The model output will estimate the probability that the candidate position error exceeds the selected threshold:
q_{t}=f_{θ}x_{t}≈Py_{t}=1 | x_{t}
Here, x_{t} is the reliability feature vector, f_{θ} is the trained model and q_{t} is the estimated unsafe-fix probability. The decision rule will be:
Accept if q_{t}≤τ_{ML}
where τ_{ML} is the decision threshold selected on validation data.
We will compare the candidate classifiers using failure-discrimination performance, calibration and computational cost. Sequence-grouped cross-validation within the training split will be used for model selection and calibration fitting. The separate validation split will be used for the final operating-threshold selection. In E0, τ_{ML} is the threshold at which the proposed policy accepts a share of fixes similar to that of the Zhang-inspired baseline on the validation sequences.
Probability calibration will be examined using Platt Scaling or Isotonic Regression. Calibration will be evaluated using reliability diagrams, Brier Score and Expected Calibration Error (ECE).
We will first train the model using visual and geometric matching features. A prior-aware version will also be trained. It adds the Euclidean distance and the Mahalanobis distance d² between the fix and the predicted position, and is used for the standalone calibrated policy in E0. Metric localization-error regression and probabilistic error prediction will remain possible alternative model formulations for further discussion with the supervisor.
4.2. Reprojection-error thresholding
Reprojection error measures how well the matched image points agree with the geometric transformation estimated during localization. For each inlier correspondence, the reprojection error is:
e_{i}=‖u_{i}−u_{i}‖_{2}
where u_{i} is the observed feature location and u_{i} is the location predicted by the estimated transformation.
The mean reprojection error is calculated over the RANSAC inliers:
e_{RPE}=1N_{i}_{i=1}N_{i}e_{i}
where N_{i} is the number of inlier correspondences. The acceptance rule is:
Accept if e_{RPE}≤τ_{RPE}
where τ_{RPE} is a pixel-error threshold selected using validation data.
This method evaluates the consistency of the estimated transformation. However, a geographically incorrect match may still produce a low reprojection error when visually similar regions generate consistent correspondences.
4.3. Zhang-inspired geometric gating
A geometric quality gate inspired by Zhang et al. [4] will be implemented using multiple indicators from the localization process. The adapted method will use match count, RANSAC inlier count, inlier ratio, mean reprojection error and the displacement between the candidate fix and the predicted position. We define:
r_{i}=N_{i}N_{m},     d_{t}=‖z_{t}−p_{t}−‖_{2}
where N_{m} is the total number of matches, N_{i} is the number of inliers, r_{i} is the inlier ratio and p_{t}− is the predicted position. The candidate measurement will be accepted when all the following conditions are satisfied:
N_{m}≥τ_{m}, N_{i}≥τ_{i}, r_{i}≥τ_{r}, e_{RPE}≤τ_{e}, d_{t}≤τ_{d}.
The thresholds will be tuned using validation data. The method will be described as Zhang-inspired because our implementation adapts the geometric quality criteria to the selected localization pipeline and dataset. Unlike reprojection-error thresholding, this approach evaluates several matching and geometric consistency conditions together.
4.4. Chi-square innovation gating
Chi-square innovation gating will be implemented as a statistical consistency test between the candidate geographic fix and the predicted position. The innovation is the difference between these two positions:
ν_{t}=z_{t}−p_{t}−
The normalized innovation squared (NIS) is:
d_{t}2=ν_{t}TS_{t}−1ν_{t}
where the innovation covariance is:
S_{t}=P_{t}−+R_{nominal}
Here, P_{t}− is the assumed covariance of the predicted position and R is the assumed covariance of the geographic measurement. For the controlled experiments, P_{t}− will be specified according to the simulated prior-uncertainty condition.R_{nominal}  will be estimated from the training sequences only, as the 2×2 second-moment matrix of the east and north errors (z − p*) of valid training fixes labelled safe (error ≤ T). Unsafe fixes are excluded, because a few errors of hundreds of metres would dominate the estimate; rejecting such fixes is the task of the reliability gate, not of the noise model. Each sequence receives equal weight. R_{nominal}is fixed for all policies and experiments. Its consistency will be checked on the validation sequences with the normalized innovation squared, whose mean should be close to 2 for a two-dimensional measurement when the covariances are correct [15]. For a two-dimensional innovation with appropriate Gaussian error and covariance assumptions, the statistic can be compared with a chi-square distribution with two degrees of freedom. Using a significance level of 0.05, the initial decision rule will be:
Accept if d_{t}2≤χ_{2}20.95≈5.99
The covariance assumptions will be documented, and their consistency with the simulated errors will be checked during validation. The nominal chi-square threshold will be kept as the statistical reference, with any additional operating-point analysis reported separately.
4.5. Additional quality indicators
Inlier count, inlier ratio and retrieval similarity will be evaluated as optional simple reliability scores. Spatial Uncertainty Estimation (SUE) [13] will be evaluated as an optional comparator if time allows. SUE uses the geographic spread of the top retrieved map candidates to estimate retrieval-level uncertainty. A large spread suggests that several geographically different regions have similar visual descriptors. SUE will be considered a retrieval uncertainty indicator rather than a direct estimate of the final metric position error. These additional methods will provide a reference for determining how much information the learned classifier gains from combining several features.
5. Navigation replay and the primary experiment (E0)
The primary E0 experiment will compare correction policies in a closed-loop sequential replay. Real UAV images will be replayed in flight order. The localization pipeline will produce candidate geographic fixes and matching records, while controlled drift will be introduced into the simulated navigation prior. The initial experiment will use a five-second localization attempt interval, moderate position drift and five fixed random seeds. The drift simulator will generate reproducible position errors using predefined bias and random-walk components. The same conditions will be used for every method. The primary comparison is between two policies that share the same filter, nominal measurement covariance and recovery logic:
Proposed policy: the calibrated unsafe-fix probability must satisfy q_{t} ≤ τ_{ML}, and the fix must then pass the chi-square test. It uses the image/matching-only feature set, since the chi-square test already checks consistency with the prediction.
Main baseline: the Zhang-inspired geometric gate, followed by the same chi-square test.
The chi-square test is shared, so any difference between the two policies comes from the gate placed before it. The chi-square test can reject a correct fix after large drift and can accept a wrong fix that happens to lie near the drifted prediction (Figure 5b); the image-based risk score is intended to catch the second case, and the shared recovery logic (Section 6) handles the first.
Four standalone policies will also be reported:
the calibrated model alone, without the chi-square test, using the prior-aware feature set (which includes the Mahalanobis distance d² of the fix from the prediction as an input)
reprojection-error thresholding
the Zhang-inspired gate alone
the chi-square test alone
The first of these shows whether the learned model needs the separate chi-square test at all.
The training data will be used to fit the reliability model and estimate necessary statistical parameters. Validation data will be used to select decision thresholds and assess probability calibration. All model configurations and thresholds will be frozen before the held-out test evaluation.
Fixed-candidate and closed-loop evaluation: We separate two evaluation modes. In the fixed-candidate evaluation, candidate records are generated once, from predefined prior offsets and search radii that do not depend on any decision, and every method scores the same records. This mode is used for RQ1 and RQ2, for threshold selection and for matching acceptance rates. In the closed-loop evaluation (E0), each policy runs its own replay. All policies start from the same initial state and receive the same images, the same drift realizations, the same localization frontend, the same filter noise and the same recovery rules. Their candidate fixes are not assumed to be identical: once two policies make different accept/reject decisions, their predicted positions differ, and so do the search window, the retrieved tiles and the following candidate fixes. E0 therefore compares whole policies rather than decisions on individual fixes. For each policy we will report fix availability and the share of attempts in which the true position lay inside the searched area. This allows differences in harmful corrections to be traced either to the decisions or to the candidates they led to. In E0, localization is run online for each policy with fixed random seeds, and results are cached so that identical queries are not recomputed.
Primary navigation metric (E0, RQ3): The sequential navigation experiment will measure how reliability decisions affect navigation accuracy. Accepted fixes will be applied with the same deterministic position-correction procedure for every policy, and the corrected position will be propagated with the recorded trajectory increments and the predefined drift. The primary metric is the number of harmful corrections per 100 scheduled localization attempts, including attempts that return NO_VALID_FIX. A correction is harmful when it increases the 2D position error by more than 5 m (Eq. 5). ATE is the guardrail. It will be reported per sequence together with its spread over the five drift seeds, and a reduction in harmful corrections counts as an improvement only if ATE does not increase beyond this spread. We will also report helpful corrections, the accepted-fix rate, position error over time, and the number of REACQUIRE and LOST episodes.
Fixed-candidate evaluation (RQ1, RQ2): This evaluation measures how effectively each method distinguishes unsafe from safe geographic measurements. For methods that produce continuous reliability scores, AUROC and AUPRC will measure failure-discrimination performance. Methods that produce only binary decisions will be evaluated at their corresponding operating points. We will also measure accepted-measurement coverage and the proportion of accepted fixes that are unsafe:
Coverage=N_{accepted}N_{valid},     Accepted Risk=N_{unsafe,accepted}N_{accepted}
Here, N_{valid} is the number of valid candidate fixes and N_{accepted} is the number accepted by the evaluated method. The ability to preserve safe measurements will be calculated as:
Safe Retention=N_{safe,accepted}N_{safe}
The proportion of unsafe fixes incorrectly accepted will also be reported:
Unsafe Acceptance Rate=N_{unsafe,accepted}N_{unsafe}
These measurements will distinguish methods that reject almost every candidate from those that preserve useful localization information. For continuous scores, we will generate risk–coverage curves by varying the decision threshold. Where possible, methods will be compared at similar accepted-measurement coverage selected on validation data. Fixed-rule baselines will be reported at their validation-selected operating points.
For the proposed probability model, calibration will be evaluated using Brier Score, Expected Calibration Error and reliability diagrams. Localization availability will be reported separately as the proportion of scheduled attempts that produce a valid geographic fix. This will keep missing measurements distinct from incorrect measurements. The results will be reported for each held-out sequence and as sequence-level averages. The five drift seeds will provide repeated simulation conditions, but they will not be treated as independent flight routes.
6. Recovery (NORMAL / REACQUIRE / LOST)
All policies use the same recovery logic with the same parameters. The logic specifies the search window, the predicted covariance, the gate applied during recovery and the conditions for changing mode.
NORMAL. The search window is centred on the predicted position, and its radius follows the innovation covariance: r = max(r_{min}, √(5.99 · λ_{max(S)})), where λ_{max(S)} is the largest eigenvalue of S. The search area and the 95% chi-square gate therefore cover the same region. Accepted fixes update the filter with R_{nominal}
Entering REACQUIRE. The system enters REACQUIRE after K consecutive scheduled attempts without an accepted fix, whether they returned NO_VALID_FIX or were rejected. We will start with K = 3.
REACQUIRE. Widening the search alone is not sufficient, because a correct fix far from the drifted prediction would still fail the chi-square test while P⁻ remains small (Figure 5b). On entering REACQUIRE, the position covariance is therefore inflated, P⁻ ← P⁻ + σ_{R}2·I, following Groves' recommendation to increase the state uncertainty [3]. σ_{R} is chosen so that the 95% gate covers the expanded search radius r_{R} (σ_{R}2 ≈ r_{R}² / 5.99), and the search window is widened to r_{R} within the onboard map. Each candidate must still pass the policy's own reliability rule. For the Zhang-inspired gate, the displacement threshold is raised to r_{R}, since a correct fix after large drift is by definition far from the prediction. For the standalone calibrated policy, d² is computed with the inflated covariance in the same way. Because the inflated gate also admits wrong fixes, a single fix does not correct the state. A location is confirmed only when M of the last N candidate fixes agree with each other within a tolerance δ after the recorded motion between them is compensated (initially 2 of 3). The confirmed fix resets the position estimate, P is reset to R_{nominal} and the system returns to NORMAL.
LOST. If no location is confirmed within a timeout, the system enters LOST. It stops applying corrections, propagates the estimate with the recorded motion while P keeps growing, and continues to search with the widest window. A location confirmed by the REACQUIRE rule returns the system to NORMAL. Time spent in LOST counts against availability.
K, r_{R}, M, N, δ and the LOST timeout will be tuned on the validation sequences, kept identical for all policies and frozen before testing. Stress tests will cover a correct but distant fix, an isolated incorrect fix and repeated wrong fixes that agree with each other. Real incorrect matching results will be used where possible, while purely synthetic examples will be identified as controlled stress tests; injected stress cases use identical injected candidates for every policy. We will measure recovery success, time to recovery and wrong confirmations (a confirmed location more than T from the true position). These results will be reported separately from E0.
7. Transfer to other datasets
The selected reliability model may be evaluated on AnyVisLoc to examine how well its reliability estimates generalize to different environments and viewing conditions. The trained model will first be tested without modification. If suitable data partitions are available, a second experiment may recalibrate the predicted probabilities using separate target-domain samples. Because AnyVisLoc includes oblique observations, camera orientation and differences in image geometry will be considered during preprocessing. A top-down transformation may be investigated when the required camera information is available. If time allows, other datasets such as UAV-VisLoc or ALTO may be included as additional experiments. Cross-dataset results will be kept separate from the primary AerialVL evaluation.
8. Jetson Orin Nano deployment
The selected localization frontend, trained reliability classifier and offline map index will be deployed on the university's NVIDIA Jetson Orin Nano. Neural feature extraction and matching components will be converted to TensorRT with FP16 precision where supported. PyTorch or ONNX Runtime will be used when conversion is impractical. For each pipeline stage, we will measure processing latency, CPU and GPU utilization, memory consumption and storage requirements. The model and map index sizes will also be recorded. Power consumption will be measured using available system tools, such as tegrastats, where supported. The evaluation will determine the computational cost of the localization and reliability framework. No fixed FPS target or flight-endurance improvement will be assumed before measurement.
9. Research questions, methods and metrics
Table 4 connects the research questions with the methods, datasets and evaluation metrics.
Table 4. Research questions and evaluation.
Research question
Method
Data
Main metrics
RQ1 – Failure discrimination
Learned classifier and geometric/statistical baselines
AerialVL  fixed-candidate records
AUROC, AUPRC, risk–coverage, accepted risk, safe retention
RQ2 – Calibration and transfer
Calibrated classifier; optional cross-dataset testing
AerialVL; AnyVisLoc if feasible
Brier, ECE, reliability diagrams
RQ3 – Sequential correction (E0)
Closed-loop replay: calibrated risk → χ² vs. Zhang-inspired gate → χ²; standalone calibrated model (no χ²), RPE, Zhang and χ² policies
AerialVL, five test sequences, five drift seeds
Harmful corrections per 100 scheduled attempts (primary); ATE (guardrail); accepted-fix rate, helpful corrections
RQ4 – Severe-drift recovery
Shared NORMAL / REACQUIRE / LOST procedure
Drift and incorrect-match stress cases
Recovery rate, recovery time, incorrect recovery
RQ5 – Jetson feasibility
Frozen localization and reliability pipeline
Test images and offline map
Latency, CPU/GPU, RAM, map/index size
10. Division of work
The project will be divided into four main work packages. Each work package will have one lead member and one supporting member, with specific responsibilities for implementation and integration.
Member A – Dataset and Evaluation: Responsible for dataset verification, coordinate conversion, train/validation/test separation and ground-truth evaluation. Member A will also implement the evaluation metrics and verify that ground-truth information is excluded from runtime features.
Member B – Visual Localization: Responsible for map preparation, retrieval, feature extraction and matching experiments, geometric verification and candidate-fix generation. Member B will define the output record format shared with the reliability and evaluation components.
Member C – Reliability and Statistical Methods: Responsible for classifier training, probability calibration, geometric and statistical comparison methods, E0 configuration and recovery evaluation. Member C will integrate the reliability methods with the candidate-fix records generated by Member B.
Member D – Embedded Deployment and Reproducibility: Responsible for Jetson deployment, computational profiling, experiment automation, software testing and reproducibility. Member D will support the integration of the localization and reliability components on the target hardware.
Table 5. Division of work.
Work package
Lead
Support
Deliverable
Dataset, coordinate system and evaluation
Member A
Member B
Verified dataset, splits, evaluation scripts
Retrieval, feature matching and localization
Member B
Member A
Localization frontend, map index, fix records
Reliability model, baselines and E0
Member C
Member D
Trained model, baselines, E0 runner
Jetson deployment and reproducibility
Member D
Member C
Jetson profile, automated tests, reproducible package
The interfaces between the work packages will be tested together. Candidate records will use a common coordinate system and feature format, allowing the different reliability methods to be evaluated using identical inputs.
Outcome and Impact (             / 20 Points)
Explain the expected outcome of your project. If it is a software product, try to include example screen designs, if it is a hardware product, try to provide detailed technical specifications, if it is research output try to explain the outcome’s contribution to the field. Also, explain the potential impacts of your results. These may be how the result will be used in real life, how it will change an existing process, or where it will be published, etc.
The project aims to develop a reproducible framework for evaluating the reliability of map-based visual position fixes in GNSS-denied UAV navigation. Using real UAV imagery, simulated navigation drift, and controlled comparisons, it will assess whether calibrated reliability estimates reduce harmful position corrections compared with existing methods. The outcomes will include an operational prototype, comparative experimental results, and embedded-platform performance measurements.
1. Deliverables
The main deliverable is a reproducible experimental framework, rather than a new navigation architecture. It will include:
D1. Dataset and geospatial preparation: Verified AerialVL sequences, georeferenced offline map tiles, and predefined training, validation, and test splits.
D2. Visual localization pipeline: An RGB-to-map localization system using image retrieval, feature matching, and geometric verification to produce metric 2D position fixes or NO_VALID_FIX, with documented runtime evidence.
D3. Reliability model and baselines: A lightweight calibrated classifier estimating the probability of an unsafe fix, together with the required comparison methods: reprojection-error thresholding, a Zhang-inspired geometric gate and chi-square innovation gating. Raw matching scores and SUE are optional additional comparators.
D4. Navigation evaluation framework: A deterministic 2D replay simulator with controlled drift, shared filtering, and NORMAL/REACQUIRE/LOST recovery logic for fair comparisons.
D5. Embedded implementation: Deployment and profiling of the localization and reliability pipeline on an NVIDIA Jetson Orin Nano, subject to hardware and software compatibility.
D6. Reproducibility package: Source code, configurations, experiment logs, evaluation scripts, final report, manuscript draft, and demonstration. Public release will respect dataset licensing restrictions.
2. Evaluation Evidence
The project will produce the following evidence:
E1. Reliability and calibration: Reliability diagrams, calibration metrics, discrimination scores, and risk–coverage comparisons.
E2. Primary comparison: Harmful corrections per 100 scheduled localization attempts for calibrated reliability plus chi-square gating versus Zhang-inspired geometric gating plus the same test, at matched validation coverage, with absolute trajectory error (ATE) as a guardrail.
E3. Navigation performance: Helpful and harmful correction rates, trajectory error over time, and sensitivity to localization frequency.
E4. Recovery performance: Recovery time and failure analysis under severe drift, isolated incorrect fixes, and persistent false matches.
E5. Embedded performance: Jetson inference time, memory use, map storage requirements, and power consumption where measurable.
E6. Generalization: An optional cross-dataset calibration assessment using AnyVisLoc, subject to data access and compatibility.
Experimental settings, statistical treatment, and evaluation procedures are specified in the Methodology.
3. Scientific Contribution
The project does not aim to introduce a new place-recognition network or navigation architecture. Its proposed contribution is an empirical assessment of whether image retrieval and geometric matching evidence can be converted into a calibrated probability of metric localization failure and whether this improves navigation decisions beyond existing geometric and statistical gates.
The study will distinguish retrieval quality, geographic fix accuracy, probability calibration, and the actual effect of corrections on navigation. It will identify the conditions under which calibrated reliability is beneficial, ineffective, or potentially detrimental. Negative or mixed results will also constitute valid findings.
4. Limitations and Prospective Use
The evaluation is limited to recorded datasets, simulated drift, and embedded-platform profiling. AerialVL's geographic coverage and the limited number of independent test sequences restrict generalization. The project does not claim autonomous flight validation, certified navigation integrity, or guaranteed performance improvements.
If effective, the proposed reliability mechanism could help inform safer use of map-based position corrections in resource-constrained UAV systems. The reusable pipeline and evaluation tools may also support future research on localization reliability.
Real UAV flights, additional datasets, PX4 integration, and publication submission are potential extensions rather than mandatory outcomes.
5. Planned Interface / Mock-up
The planned demonstration will visualize the UAV query image, retrieved map tiles and estimated fix, reliability and acceptance decisions, corrected versus drifting trajectories, position error over time, and calibration results. The accompanying mock-up illustrates the intended interface and does not represent experimental results.
