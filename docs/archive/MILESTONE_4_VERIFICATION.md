# Milestone 4 verification

Date: 2026-09-17. Actual FastAPI route/dependency stack via ASGI, with no dependency overrides. Gemini `gemini-2.5-flash`, local Weaviate (readiness HTTP 200), existing BM25 cache and cached baseline embedding/reranker models. Production top-k stays 5. No legacy retrieval, chunking/indexing or provider configuration changes.

## Exact tests

```text
.venv/bin/python -m pytest tests/unit -q
244 passed in 1.37s

.venv/bin/python -m pytest -q
244 passed, 1 deselected in 1.44s
```

The integration marker is excluded by the existing default pytest configuration. No pytest warnings. New QA tests use scripted providers/retrievers and a subprocess that blocks sockets and imports of Gemini SDKs, Weaviate, Torch and embedding/reranker modules. All existing tests pass.

## Live outcomes

| Case | Final retrieval sufficient | Result | Verification | Repair |
|---|---|---|---|---|
| A | True | answered | passed | 0 |
| B | True | answered | passed | 0 |
| C | True | answered | passed | 0 |
| D | False | insufficient_evidence | not_run | 0 |

## Stage timings (seconds)

| Case | Context | Retrieval | Grade + regrade | Rewrite | Structural lookup | Generate | Verify | Total |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| A | 0.000 | 13.060 | 8.647 | 0.000 | 0.000 | 6.030 | 5.076 | 32.814 |
| B | 1.773 | 9.455 | 25.767 | 0.000 | 0.039 | 7.807 | 9.675 | 54.517 |
| C | 0.000 | 14.034 | 51.691 | 0.000 | 0.053 | 16.836 | 19.285 | 101.900 |
| D | 0.000 | 16.878 | 25.844 | 8.113 | 0.029 | 0.000 | 0.000 | 50.864 |

These are service wall-clock measurements including any provider transport retries. Empty-history contextualization uses no LLM call. Grade includes structural regrading; total includes orchestration overhead. This is observation, not a performance refactor.

## Case A

**Original query:** Người đi bộ vào đường cao tốc bị phạt bao nhiêu?

**Standalone query:** Người đi bộ vào đường cao tốc bị phạt bao nhiêu?

**Retrieval queries:** ["Người đi bộ vào đường cao tốc bị phạt bao nhiêu?"]

**Final grade:** True; Các đoạn luật cung cấp đầy đủ thông tin về mức phạt tiền và hành vi vi phạm của người đi bộ đi vào đường cao tốc, bao gồm cả điều kiện ngoại lệ.

**Coverage:** monetary_penalty=True, subject_violation=True, condition_exception=True

**Final evidence (includes retained candidates, not all necessarily relevant):**

| Chunk ID | Citation |
|---|---|
| `chunk_c21280d75b6f8d2107221ac92b6b3efe2eae2918eab0b19c905ca7838b93aed6` | điểm a khoản 2 Điều 10 Nghị định số 168/2024/NĐ-CP |
| `chunk_6f004c0084bf61649816af6f5354a2ce136e39f42f149ea274f0d07b5472669c` | khoản 5 Điều 9 Nghị định số 168/2024/NĐ-CP |
| `chunk_1258cd3f7b6eeb0f49f5883574c4441bf4dbc8a2dd9fdf2017f9af61a1acdc82` | điểm b khoản 7 Điều 7 Nghị định số 168/2024/NĐ-CP |
| `chunk_978cdc954f928ed558f477b310b4e19a86e6195ee3baa9212446987aeb464dba` | điểm b khoản 8 Điều 8 Nghị định số 168/2024/NĐ-CP |
| `chunk_126ab222e26352138cf8716e92755245fe19c2ab8c3834f5d4cc8df28cedfbaa` | điểm a khoản 1 Điều 10 Nghị định số 168/2024/NĐ-CP |

**Published answer:**

> Người đi bộ đi vào đường cao tốc sẽ bị phạt tiền từ 400.000 đồng đến 600.000 đồng.
> Căn cứ pháp lý: điểm a khoản 2 Điều 10 Nghị định số 168/2024/NĐ-CP
>
> Quy định này không áp dụng đối với người phục vụ việc quản lý, bảo trì đường cao tốc.
> Căn cứ pháp lý: điểm a khoản 2 Điều 10 Nghị định số 168/2024/NĐ-CP

**Citations used by claims:**

- Claim 0: điểm a khoản 2 Điều 10 Nghị định số 168/2024/NĐ-CP (`chunk_c21280d75b6f8d2107221ac92b6b3efe2eae2918eab0b19c905ca7838b93aed6`)
- Claim 1: điểm a khoản 2 Điều 10 Nghị định số 168/2024/NĐ-CP (`chunk_c21280d75b6f8d2107221ac92b6b3efe2eae2918eab0b19c905ca7838b93aed6`)

**Verification:** {"status": "passed", "provenance_valid": true, "semantic_valid": true, "answer_complete": true, "issues": [], "assessments": [{"claim_index": 0, "supported": true, "reason": "Theo điểm a khoản 2 Điều 10 Nghị định số 168/2024/NĐ-CP, người đi bộ đi vào đường cao tốc sẽ bị phạt tiền từ 400.000 đồng đến 600.000 đồng."}, {"claim_index": 1, "supported": true, "reason": "Điểm a khoản 2 Điều 10 Nghị định số 168/2024/NĐ-CP quy định rõ hành vi đi vào đường cao tốc bị phạt, trừ người phục vụ việc quản lý, bảo trì đường cao tốc."}], "range_assessments": []}

**Repair attempts:** 0

## Case B

**Original query:** Còn ô tô thì sao?

**History:** [{"role": "user", "content": "Xe máy vượt đèn đỏ phạt bao nhiêu?"}]

**Standalone query:** Người điều khiển ô tô vượt đèn đỏ bị xử phạt bao nhiêu?

**Retrieval queries:** ["Người điều khiển ô tô vượt đèn đỏ bị xử phạt bao nhiêu?"]

**Final grade:** True; Các đoạn luật cung cấp đầy đủ thông tin về mức phạt tiền, số điểm bị trừ trên giấy phép lái xe và xác nhận không có hình thức xử phạt bổ sung (tước giấy phép lái xe) đối với hành vi người điều khiển ô tô vượt đèn đỏ.

**Coverage:** monetary_penalty=True, license_points=True, additional_sanction=True, subject_violation=True

**Final evidence (includes retained candidates, not all necessarily relevant):**

| Chunk ID | Citation |
|---|---|
| `chunk_5ae0ed3761e52c6858d10443fdd6340faba0eb92bb5b765bebddb9ec58084884` | điểm b khoản 9 Điều 6 Nghị định số 168/2024/NĐ-CP |
| `chunk_3bcbb72cf9fc9bec2636b13923418d150990cb87781f7ea27fa9206e4d37ccd6` | điểm g khoản 3 Điều 6 Nghị định số 168/2024/NĐ-CP |
| `chunk_6d903cb39f6dc02365950b8744379a812ed61ca0e16bd45bbab29b63d79d3dc6` | điểm b khoản 3 Điều 6 Nghị định số 168/2024/NĐ-CP |
| `chunk_f473a21bd6b0630946c6f93b9a5a6e77eb93b4f2a1f9d59c8be53ed3fa7ef375` | điểm n khoản 3 Điều 6 Nghị định số 168/2024/NĐ-CP |
| `chunk_6a0f825062e309cc4e0d18c2afd67b7d341c2ea800a31753918213302de3af8f` | điểm d khoản 2 Điều 36 Nghị định số 168/2024/NĐ-CP |
| `chunk_fbae2c31909a1844104788646730074173fe4513dedca1bfc502e65a096c4d7c` | điểm b khoản 16 Điều 6 Nghị định số 168/2024/NĐ-CP |
| `chunk_c2e7cd06070709fd7f01bfb61eb819ae25a980b91835d379490af951dc320637` | điểm a khoản 15 Điều 6 Nghị định số 168/2024/NĐ-CP |
| `chunk_45f59e16a13c196c46798f5cd4cbb49007b09db23909edce7edbe41e84c73a80` | điểm b khoản 15 Điều 6 Nghị định số 168/2024/NĐ-CP |
| `chunk_9584c2eb4e981f718e252f3b442071ecc2f6350786312a5fa102e6b97b58317b` | điểm c khoản 15 Điều 6 Nghị định số 168/2024/NĐ-CP |

**Published answer:**

> Người điều khiển xe ô tô không chấp hành hiệu lệnh của đèn tín hiệu giao thông bị phạt tiền từ 18.000.000 đồng đến 20.000.000 đồng.
> Căn cứ pháp lý: điểm b khoản 9 Điều 6 Nghị định số 168/2024/NĐ-CP
>
> Người điều khiển xe ô tô không chấp hành hiệu lệnh của đèn tín hiệu giao thông bị trừ 04 điểm trên giấy phép lái xe.
> Căn cứ pháp lý: điểm b khoản 9 Điều 6 Nghị định số 168/2024/NĐ-CP; điểm b khoản 16 Điều 6 Nghị định số 168/2024/NĐ-CP
>
> Các chunk được cung cấp không đề cập đến hình thức xử phạt bổ sung đối với hành vi người điều khiển xe ô tô không chấp hành hiệu lệnh của đèn tín hiệu giao thông.
> Căn cứ pháp lý: điểm a khoản 15 Điều 6 Nghị định số 168/2024/NĐ-CP; điểm b khoản 15 Điều 6 Nghị định số 168/2024/NĐ-CP; điểm c khoản 15 Điều 6 Nghị định số 168/2024/NĐ-CP

**Citations used by claims:**

- Claim 0: điểm b khoản 9 Điều 6 Nghị định số 168/2024/NĐ-CP (`chunk_5ae0ed3761e52c6858d10443fdd6340faba0eb92bb5b765bebddb9ec58084884`)
- Claim 1: điểm b khoản 9 Điều 6 Nghị định số 168/2024/NĐ-CP (`chunk_5ae0ed3761e52c6858d10443fdd6340faba0eb92bb5b765bebddb9ec58084884`); điểm b khoản 16 Điều 6 Nghị định số 168/2024/NĐ-CP (`chunk_fbae2c31909a1844104788646730074173fe4513dedca1bfc502e65a096c4d7c`)
- Claim 2: điểm a khoản 15 Điều 6 Nghị định số 168/2024/NĐ-CP (`chunk_c2e7cd06070709fd7f01bfb61eb819ae25a980b91835d379490af951dc320637`); điểm b khoản 15 Điều 6 Nghị định số 168/2024/NĐ-CP (`chunk_45f59e16a13c196c46798f5cd4cbb49007b09db23909edce7edbe41e84c73a80`); điểm c khoản 15 Điều 6 Nghị định số 168/2024/NĐ-CP (`chunk_9584c2eb4e981f718e252f3b442071ecc2f6350786312a5fa102e6b97b58317b`)

**Verification:** {"status": "passed", "provenance_valid": true, "semantic_valid": true, "answer_complete": true, "issues": [], "assessments": [{"claim_index": 0, "supported": true, "reason": "Khoản 9 Điều 6 Nghị định số 168/2024/NĐ-CP quy định phạt tiền từ 18.000.000 đồng đến 20.000.000 đồng đối với hành vi không chấp hành hiệu lệnh của đèn tín hiệu giao thông."}, {"claim_index": 1, "supported": true, "reason": "Điểm b khoản 16 Điều 6 Nghị định số 168/2024/NĐ-CP quy định hành vi vi phạm tại điểm b khoản 9 Điều này (không chấp hành hiệu lệnh của đèn tín hiệu giao thông) bị trừ 04 điểm giấy phép lái xe."}, {"claim_index": 2, "supported": true, "reason": "Các điểm a, b, c khoản 15 Điều 6 Nghị định số 168/2024/NĐ-CP liệt kê các hành vi bị áp dụng hình thức xử phạt bổ sung, nhưng không bao gồm hành vi không chấp hành hiệu lệnh của đèn tín hiệu giao thông (điểm b khoản 9 Điều này)."}], "range_assessments": []}

**Repair attempts:** 0

## Case C

**Original query:** Ô tô vượt quá tốc độ từ 20 đến 35 km/h bị xử phạt thế nào?

**Standalone query:** Ô tô vượt quá tốc độ từ 20 đến 35 km/h bị xử phạt thế nào?

**Retrieval queries:** ["Ô tô vượt quá tốc độ từ 20 đến 35 km/h bị xử phạt thế nào?"]

**Final grade:** True; Các đoạn luật cung cấp đầy đủ thông tin về mức phạt tiền, điểm trừ giấy phép lái xe và xác định không có hình thức xử phạt bổ sung cho hành vi ô tô vượt quá tốc độ từ 20 đến 35 km/h, bao gồm cả điểm 20 km/h và khoảng trên 20 km/h đến 35 km/h.

**Coverage:** monetary_penalty=True, license_points=True, additional_sanction=True, subject_violation=True, threshold_range=True

**Final evidence (includes retained candidates, not all necessarily relevant):**

| Chunk ID | Citation |
|---|---|
| `chunk_a79291b3dad755130b6fd39a04c42a738cc7cd2204ba6049136ad8edea29d4c4` | điểm a khoản 6 Điều 6 Nghị định số 168/2024/NĐ-CP |
| `chunk_7275f6dada946ad4b7fea7ca23371e80af968c101eeb28c68628fc5d77f3dc8a` | điểm a khoản 7 Điều 6 Nghị định số 168/2024/NĐ-CP |
| `chunk_88b3144ee420da9d1395b879c054ad17057c62aa4602cbfe1f8a5e5d9a746ec4` | điểm a khoản 8 Điều 7 Nghị định số 168/2024/NĐ-CP |
| `chunk_3055016426770fb75aebc4fc862de5691ecc57dbd064653229d56690a8b3480b` | điểm đ khoản 5 Điều 6 Nghị định số 168/2024/NĐ-CP |
| `chunk_9bda3a038f8882860d7cd0f7fc4035fa020f73374088dfc76d8bd4aef276147f` | điểm a khoản 4 Điều 7 Nghị định số 168/2024/NĐ-CP |
| `chunk_b17a214485b66bcdc40d640446bc103e289389c88c57abce41a78e2f7159885e` | điểm a khoản 16 Điều 6 Nghị định số 168/2024/NĐ-CP |
| `chunk_fbae2c31909a1844104788646730074173fe4513dedca1bfc502e65a096c4d7c` | điểm b khoản 16 Điều 6 Nghị định số 168/2024/NĐ-CP |
| `chunk_c2e7cd06070709fd7f01bfb61eb819ae25a980b91835d379490af951dc320637` | điểm a khoản 15 Điều 6 Nghị định số 168/2024/NĐ-CP |
| `chunk_45f59e16a13c196c46798f5cd4cbb49007b09db23909edce7edbe41e84c73a80` | điểm b khoản 15 Điều 6 Nghị định số 168/2024/NĐ-CP |
| `chunk_9584c2eb4e981f718e252f3b442071ecc2f6350786312a5fa102e6b97b58317b` | điểm c khoản 15 Điều 6 Nghị định số 168/2024/NĐ-CP |

**Published answer:**

> Đối với người điều khiển xe ô tô chạy quá tốc độ quy định trên 20 km/h đến 35 km/h, sẽ bị phạt tiền từ 6.000.000 đồng đến 8.000.000 đồng.
> Căn cứ pháp lý: điểm a khoản 6 Điều 6 Nghị định số 168/2024/NĐ-CP
>
> Người điều khiển xe ô tô chạy quá tốc độ quy định trên 20 km/h đến 35 km/h còn bị trừ 04 điểm trên giấy phép lái xe.
> Căn cứ pháp lý: điểm a khoản 6 Điều 6 Nghị định số 168/2024/NĐ-CP; điểm b khoản 16 Điều 6 Nghị định số 168/2024/NĐ-CP
>
> Đối với người điều khiển xe ô tô chạy quá tốc độ quy định đúng 20 km/h, sẽ bị phạt tiền từ 4.000.000 đồng đến 6.000.000 đồng.
> Căn cứ pháp lý: điểm đ khoản 5 Điều 6 Nghị định số 168/2024/NĐ-CP
>
> Người điều khiển xe ô tô chạy quá tốc độ quy định đúng 20 km/h còn bị trừ 02 điểm trên giấy phép lái xe.
> Căn cứ pháp lý: điểm đ khoản 5 Điều 6 Nghị định số 168/2024/NĐ-CP; điểm a khoản 16 Điều 6 Nghị định số 168/2024/NĐ-CP

**Citations used by claims:**

- Claim 0: điểm a khoản 6 Điều 6 Nghị định số 168/2024/NĐ-CP (`chunk_a79291b3dad755130b6fd39a04c42a738cc7cd2204ba6049136ad8edea29d4c4`)
- Claim 1: điểm a khoản 6 Điều 6 Nghị định số 168/2024/NĐ-CP (`chunk_a79291b3dad755130b6fd39a04c42a738cc7cd2204ba6049136ad8edea29d4c4`); điểm b khoản 16 Điều 6 Nghị định số 168/2024/NĐ-CP (`chunk_fbae2c31909a1844104788646730074173fe4513dedca1bfc502e65a096c4d7c`)
- Claim 2: điểm đ khoản 5 Điều 6 Nghị định số 168/2024/NĐ-CP (`chunk_3055016426770fb75aebc4fc862de5691ecc57dbd064653229d56690a8b3480b`)
- Claim 3: điểm đ khoản 5 Điều 6 Nghị định số 168/2024/NĐ-CP (`chunk_3055016426770fb75aebc4fc862de5691ecc57dbd064653229d56690a8b3480b`); điểm a khoản 16 Điều 6 Nghị định số 168/2024/NĐ-CP (`chunk_b17a214485b66bcdc40d640446bc103e289389c88c57abce41a78e2f7159885e`)

**Verification:** {"status": "passed", "provenance_valid": true, "semantic_valid": true, "answer_complete": true, "issues": [], "assessments": [{"claim_index": 0, "supported": true, "reason": "Nguồn \"điểm a khoản 6 Điều 6 Nghị định số 168/2024/NĐ-CP\" quy định phạt tiền từ 6.000.000 đồng đến 8.000.000 đồng đối với người điều khiển xe ô tô chạy quá tốc độ quy định trên 20 km/h đến 35 km/h."}, {"claim_index": 1, "supported": true, "reason": "Nguồn \"điểm b khoản 16 Điều 6 Nghị định số 168/2024/NĐ-CP\" quy định hành vi vi phạm tại khoản 6 Điều 6 (bao gồm chạy quá tốc độ trên 20 km/h đến 35 km/h) sẽ bị trừ 04 điểm giấy phép lái xe."}, {"claim_index": 2, "supported": true, "reason": "Nguồn \"điểm đ khoản 5 Điều 6 Nghị định số 168/2024/NĐ-CP\" quy định phạt tiền từ 4.000.000 đồng đến 6.000.000 đồng đối với người điều khiển xe ô tô chạy quá tốc độ quy định từ 10 km/h đến 20 km/h, bao gồm trường hợp đúng 20 km/h."}, {"claim_index": 3, "supported": true, "reason": "Nguồn \"điểm a khoản 16 Điều 6 Nghị định số 168/2024/NĐ-CP\" quy định hành vi vi phạm tại khoản 5 Điều 6 (bao gồm chạy quá tốc độ từ 10 km/h đến 20 km/h) sẽ bị trừ 02 điểm giấy phép lái xe."}], "range_assessments": [{"branch_index": 0, "addressed": true, "reason": "Các claims 0 và 1 đã trả lời về mức phạt tiền và điểm trừ cho hành vi vượt quá tốc độ trên 20 km/h đến 35 km/h.", "chunk_id": "chunk_a79291b3dad755130b6fd39a04c42a738cc7cd2204ba6049136ad8edea29d4c4"}, {"branch_index": 1, "addressed": true, "reason": "Các claims 2 và 3 đã trả lời về mức phạt tiền và điểm trừ cho hành vi vượt quá tốc độ đúng 20 km/h.", "chunk_id": "chunk_3055016426770fb75aebc4fc862de5691ecc57dbd064653229d56690a8b3480b"}]}

**Repair attempts:** 0

## Case D

**Original query:** Ô tô vượt đèn đỏ có bị tước giấy phép lái xe không?

**Standalone query:** Ô tô vượt đèn đỏ có bị tước giấy phép lái xe không?

**Retrieval queries:** ["Ô tô vượt đèn đỏ có bị tước giấy phép lái xe không?", "Chế tài tước giấy phép lái xe ô tô vượt đèn đỏ"]

**Final grade:** False; Các đoạn luật cung cấp hành vi vi phạm của ô tô vượt đèn đỏ (không chấp hành hiệu lệnh của đèn tín hiệu giao thông) nhưng không có căn cứ cho thấy hành vi này bị tước giấy phép lái xe. Khoản 15 Điều 6 liệt kê các hành vi bị tước giấy phép lái xe nhưng không bao gồm hành vi tại khoản 9 Điều 6.

**Coverage:** additional_sanction=False, subject_violation=True

**Final evidence (includes retained candidates, not all necessarily relevant):**

| Chunk ID | Citation |
|---|---|
| `chunk_e3a68d1d13d236020bc2b3b94ce9a8eea3a2f193a4e9433a76437f2df9a6f3b0` | điểm a khoản 5 Điều 6 Nghị định số 168/2024/NĐ-CP |
| `chunk_5ae0ed3761e52c6858d10443fdd6340faba0eb92bb5b765bebddb9ec58084884` | điểm b khoản 9 Điều 6 Nghị định số 168/2024/NĐ-CP |
| `chunk_4274ce07a33c1dc838b570e0bc063373d077512ca03560bf6ac112e84e614434` | điểm b khoản 1 Điều 7 Nghị định số 168/2024/NĐ-CP |
| `chunk_6a0f825062e309cc4e0d18c2afd67b7d341c2ea800a31753918213302de3af8f` | điểm d khoản 2 Điều 36 Nghị định số 168/2024/NĐ-CP |
| `chunk_3bcbb72cf9fc9bec2636b13923418d150990cb87781f7ea27fa9206e4d37ccd6` | điểm g khoản 3 Điều 6 Nghị định số 168/2024/NĐ-CP |
| `chunk_c2e7cd06070709fd7f01bfb61eb819ae25a980b91835d379490af951dc320637` | điểm a khoản 15 Điều 6 Nghị định số 168/2024/NĐ-CP |
| `chunk_45f59e16a13c196c46798f5cd4cbb49007b09db23909edce7edbe41e84c73a80` | điểm b khoản 15 Điều 6 Nghị định số 168/2024/NĐ-CP |
| `chunk_9584c2eb4e981f718e252f3b442071ecc2f6350786312a5fa102e6b97b58317b` | điểm c khoản 15 Điều 6 Nghị định số 168/2024/NĐ-CP |

**Published answer:**

`answer: null`. Chưa truy xuất đủ căn cứ để trả lời an toàn; điều này không có nghĩa chế tài không tồn tại.

No normal legal answer was published.

**Verification:** {"status": "not_run", "provenance_valid": null, "semantic_valid": null, "answer_complete": null, "issues": [], "assessments": [], "range_assessments": []}

**Repair attempts:** 0

## Reproduced failures and changes

- First live batch, case A: the grader invented a `range_coverage` question quote for a monetary amount not stated in the question. Existing grounding validation raised `ValueError`. Clarified grading prompt: prove only an explicit question threshold, and classify irrelevant aspects with `required=false`; range validation was not relaxed. Subsequent A runs passed.
- First batch, case C: structural expansion added both license-point leaves, but regrade changed the exact-boundary leaf to incompatible. Final retrieval was insufficient and generation was correctly skipped. This is an upstream grader false negative, not evidence absence.
- Confirmation batch, case C: the generator omitted the inclusive lower boundary; the original global completeness check incorrectly passed. That result is NOT accepted as successful verification. Added proven range branches to generation/verifier input, deterministic required-source checks, and mandatory per-branch semantic assessments. Regression rejects the reproduced upper-only answer before any verifier call.
- Next C run: the generated answer preserved both boundary branches and all individual claims were supported, but the verifier mistyped a long source hash. Strict checking rejected the response and published no answer. Replaced verifier hash copying with integer branch indices and server-side source-ID resolution; no fuzzy matching or acceptance of unknown IDs.
- Case D's latest insufficient result is valid: complete clause-15 leaves do not establish complete applicable-rule provenance. The final pool had eight chunks, including all three clause-15 leaves but no clause-16 license-point leaf; the referenced conduct clauses were also absent. A historical confirmation emitted a source-absence statement, which is not proof of legal non-applicability. These live traces predate the support-state contract; do not claim a grounded negative D answer is verified.

## Remaining limits

Semantic support and evidence grading remain model judgments; false negatives and correlated model mistakes are still possible. Deterministic provenance and mandatory range coverage prevent the specific reproduced false positive but are not formal legal proof. Case D remains unknown until trusted applicable-rule provenance exists. The subsequent support-state contract blocks represented negative/unknown claims and assessments deterministically, including optimistic model booleans; no production negative-support authority has been fabricated. The offline support-state regressions do not constitute a new Gemini live run.

No LangGraph or answer repair loop: one generation and at most one semantic verification; any verification failure publishes `answer: null`. Infrastructure errors propagate. No next milestone, persistence, frontend, retrieval replacement or broad optimization work was started.

Local full traces (not containing API credentials): `/tmp/roadlawqa_m4_live.json`, `/tmp/roadlawqa_m4_confirmation.json`, `/tmp/roadlawqa_m4_final.json`, `/tmp/roadlawqa_m4_range_final.json`. The outcomes above retain failed runs rather than counting fluent or optimistic model outputs as success.

## Files changed

Modified:

- `ai/prompts/evidence_grading.py`
- `backend/main.py`
- `backend/services/agentic_retrieval.py`

Created:

- `ai/agent/answer_generator.py`
- `ai/agent/citation_verifier.py`
- `ai/prompts/answer_generation.py`
- `ai/prompts/citation_verification.py`
- `backend/api/v1/answer.py`
- `backend/dependencies/answer.py`
- `backend/schemas/answer.py`
- `backend/services/answer.py`
- `tests/unit/test_grounded_answer.py`
- `docs/MILESTONE_4.md`
- `docs/MILESTONE_4_VERIFICATION.md`

`git diff --check` passed. All protected legacy files have an empty diff.
The tracked diff reports 3 files changed, 35 insertions and 2 deletions; the 11
new files are untracked and therefore not included in `git diff --stat`.
No files were staged or committed.
