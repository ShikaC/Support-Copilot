# 完整业务 API 实测与公开参考对照

同一批 32 个 Doc2Dial 人工构建的公开对话，分别在 1/2/4 并发下运行。原始参考回复和文档标注来自数据集发布者；不是本项目 AI 生成的标准答案。全部 488 份文档参与检索。

| 并发工单 | API 返回 | 结果读回匹配 | live 成功 | 无证据降级 | 其他降级 | 创建至分析保存 p50 | p95 | 完成操作/秒 | live 操作/秒 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 1 | 32/32 | 32/32 | 22/32 | 4 | 6 | 10.78s | 20.86s | 0.079 | 0.055 |
| 2 | 32/32 | 32/32 | 26/32 | 6 | 0 | 9.39s | 18.39s | 0.183 | 0.149 |
| 4 | 32/32 | 32/32 | 16/32 | 4 | 12 | 16.94s | 20.93s | 0.244 | 0.122 |

完成操作吞吐包括降级结果；live 操作也不等于客户问题已解决。固定并发的短批次不是最大容量测试；顺序运行的组间差异还可能受网关负载和缓存影响。API 计时含真实 HTTP 与落库，不含浏览器渲染和人工审核；readback 原始耗时也已保存。

| 并发 | 有真实检索记录 | 命中发布者参考文档 | 标注证据字符覆盖均值 | 全覆盖题数 | 回复 token F1（全部/仅 live） |
| --- | ---: | ---: | ---: | ---: | ---: |
| 1 | 32/32 | 19/32 (59.4%) | 49.9% | 15/32 | 11.9% / 17.4% |
| 2 | 32/32 | 19/32 (59.4%) | 49.9% | 15/32 | 14.6% / 18.0% |
| 4 | 32/32 | 19/32 (59.4%) | 49.9% | 15/32 | 8.1% / 16.2% |

质量主组为并发 1；其余是同题重复观察。文档命中是 Top 3 是否含发布者标注文档；字符覆盖为原始 Unicode 区间交并，重叠不重复计数。它们不是事实正确率。token F1 只衡量词语重叠，去除数字引用、标点和英语冠词；较长但有据的回答可能得分较低。非 live 结果的 F1 记为 0，另列仅 live 均值，避免只看幸存请求。

原始数据中存在寒暄和上下文不明确的首轮输入，例如 “Hi there” 也关联了业务文档片段。所有样本均保留，没有看过结果后删题；因此这些数字是冻结抽样协议下的参考对照，不足以证明真实客服问题解决率。

## 逐题参考与最终业务输出

### d2d-d5b3085e911cd9d578f25c007f1205fc-2 · dmv

**问题：** I need information about how much it'll cost me to renew my license.

**发布者参考回复：** Your renewal fee is either on the renewal application that we will mail you or displayed before you pay online. It depends on what type of license you have.

**发布者标注文档片段：**

> Your renewal fee is on the renewal application we mail you and displayed before you pay online. 
> They are also listed on the chart below for different types of licenses. 
> The fees listed include the photo document fee and the supplemental Metropolitan Commuter Transportation District MCTD fee, if required. 

**并发 1：** live；无降级原因；参考文档命中 true；证据覆盖 100.0%；创建至分析保存 10.55s

[原始请求结果](/Users/shika/Documents/Support-Copilot/docs/verification/business-benchmark-2026-09-10/run-1/trials/c1-d2d-d5b3085e911cd9d578f25c007f1205fc-2.json)

> The exact renewal cost is shown on the renewal application mailed to you and before you pay online. The amount depends on factors such as your license type, term, location, and any applicable additional fees. The archived information lists a $30 additional fee for an Enhanced Driver License (EDL) and an MCTD fee of $1 for every six months in effect for residents of specified counties. The supplied archive excerpt does not include the full fee chart, so it does not provide your exact total. This information is from the archived document and has not been verified against current policy. [1][2]

**并发 2：** live；无降级原因；参考文档命中 true；证据覆盖 100.0%；创建至分析保存 10.74s

[原始请求结果](/Users/shika/Documents/Support-Copilot/docs/verification/business-benchmark-2026-09-10/run-1/trials/c2-d2d-d5b3085e911cd9d578f25c007f1205fc-2.json)

> According to the archived information, your exact renewal fee is shown on the renewal application mailed to you and displayed before you pay online. The amount varies by license type. An Enhanced Driver License adds $30, while a REAL ID has no additional fee beyond the normal renewal fee. If applicable, the MCTD fee is $1 per six months of validity ($16 for an 8-year license). [1][2]

**并发 4：** fallback；structured_generation_response_timeout；参考文档命中 true；证据覆盖 100.0%；创建至分析保存 20.37s

[原始请求结果](/Users/shika/Documents/Support-Copilot/docs/verification/business-benchmark-2026-09-10/run-1/trials/c4-d2d-d5b3085e911cd9d578f25c007f1205fc-2.json)

> I do not have sufficient verified evidence to answer this request. A support specialist needs to review it before any action or commitment.

### d2d-18989f5d45b3c2fda47c95314de762e8-2 · dmv

**问题：** hello I need information on Empire Gold plates

**发布者参考回复：** Since April 1, 2010, DMV has issued Empire Gold vehicle license plates. The DMV no longer issues Empire Blue and White plates.

**发布者标注文档片段：**

> Since April 1 , 2010 , 
> DMV has issued Empire Gold vehicle license plates. 
> DMV no longer issues Empire Blue and White plates. 

**并发 1：** live；无降级原因；参考文档命中 true；证据覆盖 100.0%；创建至分析保存 9.41s

[原始请求结果](/Users/shika/Documents/Support-Copilot/docs/verification/business-benchmark-2026-09-10/run-1/trials/c1-d2d-18989f5d45b3c2fda47c95314de762e8-2.json)

> According to the archived information, Empire Gold vehicle plates have been issued since April 1, 2010, and you do not have to replace your current plates when renewing registration. You can order Empire Gold plates online, by phone, or at a DMV office. The fee is $25 for a set of two plates or $12.50 for a single-plate vehicle; an additional $3.75 exchange fee applies when ordering outside a registration renewal. In eligible vehicle classes, keeping the same plate number costs an additional $20, although personalized plate holders do not pay that extra fee. When you receive the new plates, deface and recycle the old plates according to local guidelines rather than returning them to the DMV. This information comes from the supplied archive and has not been verified as current policy. [1][2][3]

**并发 2：** live；无降级原因；参考文档命中 true；证据覆盖 100.0%；创建至分析保存 9.37s

[原始请求结果](/Users/shika/Documents/Support-Copilot/docs/verification/business-benchmark-2026-09-10/run-1/trials/c2-d2d-18989f5d45b3c2fda47c95314de762e8-2.json)

> According to the supplied archive, Empire Gold vehicle plates have been issued since April 1, 2010, and Empire Blue and White plates are no longer issued. You do not have to replace your current plates when renewing; you may keep them or order Empire Gold plates.
> 
> You can order Empire Gold plates by phone, online, or at a DMV office. Online orders require the vehicle plate number, vehicle class, name, and ZIP Code on DMV records.
> 
> Fees listed in the archive are $25 for a two-plate set, $12.50 for a single-plate vehicle, and an additional $3.75 exchange fee when ordering outside a registration renewal. Keeping the same eligible plate number generally costs an additional $20, although personalized plates have different fee treatment described in the archive. [1][2]

**并发 4：** fallback；structured_generation_response_timeout；参考文档命中 true；证据覆盖 100.0%；创建至分析保存 20.82s

[原始请求结果](/Users/shika/Documents/Support-Copilot/docs/verification/business-benchmark-2026-09-10/run-1/trials/c4-d2d-18989f5d45b3c2fda47c95314de762e8-2.json)

> I do not have sufficient verified evidence to answer this request. A support specialist needs to review it before any action or commitment.

### d2d-0d1e2258170c7b120931e7c6144ff931-2 · dmv

**问题：** Can you answer some questions I have about my suspended driving privilege, please?

**发布者参考回复：** A suspension means your license or driving privilege will be taken away for a period of time. You may need to pay a suspension termination fee. our suspension period can be definite which has a beginning and end date or indefinite, which does not end until you take a required action.

**发布者标注文档片段：**

> A suspension means your license or driving privilege will be taken away for a period of time. 
> You may need to pay a suspension termination fee [1]. 
> Your suspension period can be definite which has a beginning and end date or indefinite, which does not end until you take a required action. 

**并发 1：** live；无降级原因；参考文档命中 true；证据覆盖 0.0%；创建至分析保存 10.59s

[原始请求结果](/Users/shika/Documents/Support-Copilot/docs/verification/business-benchmark-2026-09-10/run-1/trials/c1-d2d-0d1e2258170c7b120931e7c6144ff931-2.json)

> Yes. The archived information indicates that you can check whether your license or driving privilege is suspended or revoked by signing up for MyDMV and using the “My License, Permit or ID” service. A driving record may show the sanction date, reason, order or case number, affected class, any civil penalty or termination fee, sanction length, and clearance information. If the privilege was revoked, the license is canceled; after the revocation period ends, you generally must request DMV approval before applying for a new license, and additional testing or fees may be required. Please provide your specific questions or the notice language, and I can explain it based on the archived information. This response does not verify current policy or your individual status. [1][2]

**并发 2：** live；无降级原因；参考文档命中 true；证据覆盖 0.0%；创建至分析保存 10.68s

[原始请求结果](/Users/shika/Documents/Support-Copilot/docs/verification/business-benchmark-2026-09-10/run-1/trials/c2-d2d-0d1e2258170c7b120931e7c6144ff931-2.json)

> Yes. Please tell me what you would like to know about the suspension—for example, how to check whether your driving privilege is suspended, the reason for the suspension, how to determine whether it has been cleared, or what steps may be required for restoration. Based on the archived information, you can check your status through MyDMV’s “My License, Permit or ID” service. A driving privilege is the legal authority to drive in a state other than the state that issued your license, so an out-of-state license may remain valid elsewhere even if your privilege to drive in New York is revoked. This response is based on the supplied archived documents; current policy has not been verified. [1]

**并发 4：** live；无降级原因；参考文档命中 true；证据覆盖 0.0%；创建至分析保存 9.57s

[原始请求结果](/Users/shika/Documents/Support-Copilot/docs/verification/business-benchmark-2026-09-10/run-1/trials/c4-d2d-0d1e2258170c7b120931e7c6144ff931-2.json)

> Yes. I can help answer questions about your suspended driving privilege using the archived information provided. You can check whether your license or driving privilege is suspended or revoked by signing up for MyDMV and using the “My License, Permit or ID” service. Please send your specific questions or the wording of any DMV notice. This response is based on the supplied archive; current policy has not been verified. [1]

### d2d-91504908b965f7beba2fcfc4cd523dfc-2 · dmv

**问题：** Can DMV see my searches?

**发布者参考回复：** Yes, they may ask about performed searches.

**发布者标注文档片段：**

> Yes , 
> DMV may ask you about a DIAL - IN search you performed. 
> We inquire about searches to monitor compliance with the DIAL - IN Terms of Service . You must respond to the inquiry whether or not you have business records that support your search. 

**并发 1：** live；无降级原因；参考文档命中 true；证据覆盖 95.5%；创建至分析保存 9.10s

[原始请求结果](/Users/shika/Documents/Support-Copilot/docs/verification/business-benchmark-2026-09-10/run-1/trials/c1-d2d-91504908b965f7beba2fcfc4cd523dfc-2.json)

> According to the supplied archived documents, yes. DMV logs searches performed through its search accounts and monitors them for compliance. If a motorist asks whether their records were searched, DMV may provide the search account holder’s name and business address, along with the time, date, and search criteria. The archive does not represent that current policy has been independently verified. [1][2]

**并发 2：** live；无降级原因；参考文档命中 true；证据覆盖 95.5%；创建至分析保存 9.24s

[原始请求结果](/Users/shika/Documents/Support-Copilot/docs/verification/business-benchmark-2026-09-10/run-1/trials/c2-d2d-91504908b965f7beba2fcfc4cd523dfc-2.json)

> Yes. According to the archived document, search records are public. If a motorist asks the DMV whether their records were searched, the DMV provides the DIAL-IN account holder’s name and business address, as well as the time, date, and search criteria used. The account number itself is not disclosed. This response is based on the supplied archive; current policy was not independently verified. [1]

**并发 4：** live；无降级原因；参考文档命中 true；证据覆盖 95.5%；创建至分析保存 17.16s

[原始请求结果](/Users/shika/Documents/Support-Copilot/docs/verification/business-benchmark-2026-09-10/run-1/trials/c4-d2d-91504908b965f7beba2fcfc4cd523dfc-2.json)

> According to the supplied archived information, yes. DMV logs searches, and search records are described as public records. If a motorist asks whether their records were searched, DMV may provide the DIAL-IN account holder’s name and business address, along with the time, date, and search criteria. The account number itself is not disclosed. This response is based on the supplied archive and does not verify current policy. [1][2]

### d2d-edd5419f19cd561e19be436560209329-2 · dmv

**问题：** I need some guidance with replacing a non-driver ID card. Can you help me?

**发布者参考回复：** Of course. You can replace your non-driver ID if it was lost or destroyed, or after you update your address. You can not replace your ID if it expired you must renew or apply for a new one.

**发布者标注文档片段：**

> You can replace your non - driver ID if it was lost or destroyed, or after you update your address. 
> You cannot replace your ID if it expired you must renew or apply for a new one. 

**并发 1：** live；无降级原因；参考文档命中 true；证据覆盖 100.0%；创建至分析保存 12.00s

[原始请求结果](/Users/shika/Documents/Support-Copilot/docs/verification/business-benchmark-2026-09-10/run-1/trials/c1-d2d-edd5419f19cd561e19be436560209329-2.json)

> Yes. Based on the archived DMV guidance, you can replace a non-driver ID if it was lost, destroyed, or you updated your address. If the ID has expired, you must renew or apply for a new one instead.
> 
> Available options:
> - Online: Available if you already have an Enhanced or REAL ID, or want to keep a Standard document. A replacement Standard document will show “NOT FOR FEDERAL PURPOSES.”
> - By mail: Submit form MV-44, photocopies of acceptable identity documents, and payment by check or money order as instructed in the archived guidance.
> - At a DMV office: Recommended if you want an Enhanced or REAL ID, or if you need changes other than an address change.
> - From overseas: Replacement must be completed by mail using form MV-44, identity-document photocopies, and the appropriate fee.
> 
> If you plan to travel domestically, review the Enhanced/REAL ID requirements before choosing to keep a Standard document. This response is based on the supplied archived documents; current requirements were not verified. [1][2]

**并发 2：** live；无降级原因；参考文档命中 true；证据覆盖 100.0%；创建至分析保存 12.12s

[原始请求结果](/Users/shika/Documents/Support-Copilot/docs/verification/business-benchmark-2026-09-10/run-1/trials/c2-d2d-edd5419f19cd561e19be436560209329-2.json)

> Based on the archived guidance, you may replace a non-driver ID card if it was lost, destroyed, or you updated your address. If the card has expired, you must renew it or apply for a new one instead.
> 
> Available options:
> - Online: Available if you already have an Enhanced or REAL ID, or want to keep a Standard document.
> - By mail: Submit form MV-44, photocopies of acceptable identity documents, and the applicable payment.
> - DMV office: Use this option for changes other than an address change, or if you want to replace the card in person.
> - Overseas: Replacement must be completed by mail.
> 
> If you want the replacement mailed to an alternate address, follow the archived instructions: include a separate note with the alternate address and do not write it on form MV-44. The archive also notes that a Standard document may be marked “NOT FOR FEDERAL PURPOSES,” and recommends considering an Enhanced or REAL ID if you plan to travel. This response is based on the supplied archived documents; current requirements were not verified. [1][2]

**并发 4：** live；无降级原因；参考文档命中 true；证据覆盖 100.0%；创建至分析保存 12.20s

[原始请求结果](/Users/shika/Documents/Support-Copilot/docs/verification/business-benchmark-2026-09-10/run-1/trials/c4-d2d-edd5419f19cd561e19be436560209329-2.json)

> Yes. Based on the supplied archived DMV guidance:
> 
> - You can replace a non-driver ID if it was lost, destroyed, or you updated your address.
> - If the ID has expired, you cannot replace it; you must renew it or apply for a new one.
> - You may replace it online if you already have an Enhanced or REAL ID, or if you want to keep a Standard ID. A Standard ID replaced online will be marked “NOT FOR FEDERAL PURPOSES.”
> - You may also apply by mail using form MV-44, photocopies of acceptable identity documents, and the required payment.
> - If you are overseas, replacement must be completed by mail.
> - Changes other than an address change require an in-person DMV office visit.
> 
> If you want the replacement sent to an alternate address, follow the archived instructions carefully; online orders cannot be sent to a different address. [1][2]

### d2d-efcaa7a28676c6ac14d8fe1ad74e39c1-2 · dmv

**问题：** I need help with a road test.

**发布者参考回复：** Schedule an appointment online.

**发布者标注文档片段：**

> Use the DMV Road test system to schedule confirm, cancel or reschedule a driving skills road test including CDL and motorcycle online or by phone. 

**并发 1：** live；无降级原因；参考文档命中 false；证据覆盖 0.0%；创建至分析保存 7.92s

[原始请求结果](/Users/shika/Documents/Support-Copilot/docs/verification/business-benchmark-2026-09-10/run-1/trials/c1-d2d-efcaa7a28676c6ac14d8fe1ad74e39c1-2.json)

> To prepare for your road test, practice smooth steering, moderate acceleration, gentle braking, and using the correct gear. Follow posted speed limits and adjust your speed for weather, visibility, road, and traffic conditions. Maintain an adequate following distance, using the two-second rule and increasing it in poor conditions. Consistently obey traffic signs, signals, and pavement markings; stop before intersections, stop lines, and crosswalks when required. Practice proper lane selection and positioning, use turn signals or the horn appropriately, and check your mirrors while watching for hazards around you. [1]

**并发 2：** live；无降级原因；参考文档命中 false；证据覆盖 0.0%；创建至分析保存 15.61s

[原始请求结果](/Users/shika/Documents/Support-Copilot/docs/verification/business-benchmark-2026-09-10/run-1/trials/c2-d2d-efcaa7a28676c6ac14d8fe1ad74e39c1-2.json)

> For your road test, practice:
> 
> - Steering smoothly when driving straight, turning, and backing up.
> - Accelerating moderately without racing the engine or stalling.
> - Braking gently and stopping in the correct lane position.
> - Selecting the correct gear and shifting smoothly, if using a manual transmission.
> - Obeying speed limits and adjusting speed for weather, visibility, road, and traffic conditions.
> - Maintaining a safe following distance, increasing it in poor weather or visibility.
> - Understanding and consistently obeying traffic signs, signals, and pavement markings.
> - Stopping before the intersection, stop line, or crosswalk when required.
> - Staying in the proper lane, especially before turns.
> - Using turn signals or the horn appropriately to communicate.
> - Checking mirrors frequently and watching for hazards around, behind, and beside you.
> 
> This guidance comes from the supplied archive; current road-test requirements were not verified. [1]

**并发 4：** live；无降级原因；参考文档命中 false；证据覆盖 0.0%；创建至分析保存 13.43s

[原始请求结果](/Users/shika/Documents/Support-Copilot/docs/verification/business-benchmark-2026-09-10/run-1/trials/c4-d2d-efcaa7a28676c6ac14d8fe1ad74e39c1-2.json)

> Based on the supplied archived guidance, practice:
> 
> - Smooth steering when driving straight, turning, and backing up.
> - Moderate, smooth acceleration without racing the engine or stalling.
> - Gentle braking and stopping in the correct lane position.
> - Selecting the correct gear and shifting properly.
> - Obeying speed limits and adjusting speed for weather, visibility, and traffic.
> - Maintaining a safe following distance, increasing it in poor conditions.
> - Understanding and consistently obeying traffic signs, signals, and pavement markings.
> - Stopping before the intersection, stop line, or crosswalk when required.
> - Staying in the proper lane, especially before turning.
> - Using turn signals or the horn appropriately to communicate.
> - Checking mirrors frequently and watching for hazards around your vehicle. [1]

### d2d-7eb233e7681db759178fbe3a2cbe8c60-2 · dmv

**问题：** Hi there

**发布者参考回复：** How can I help you?

**发布者标注文档片段：**

> You do not need an eye exam when you replace your document. 

**并发 1：** fallback；structured_generation_response_timeout；参考文档命中 false；证据覆盖 0.0%；创建至分析保存 20.39s

[原始请求结果](/Users/shika/Documents/Support-Copilot/docs/verification/business-benchmark-2026-09-10/run-1/trials/c1-d2d-7eb233e7681db759178fbe3a2cbe8c60-2.json)

> I do not have sufficient verified evidence to answer this request. A support specialist needs to review it before any action or commitment.

**并发 2：** fallback；insufficient_evidence；参考文档命中 false；证据覆盖 0.0%；创建至分析保存 7.39s

[原始请求结果](/Users/shika/Documents/Support-Copilot/docs/verification/business-benchmark-2026-09-10/run-1/trials/c2-d2d-7eb233e7681db759178fbe3a2cbe8c60-2.json)

> I do not have sufficient verified evidence to answer this request. A support specialist needs to review it before any action or commitment.

**并发 4：** fallback；structured_generation_response_timeout；参考文档命中 false；证据覆盖 0.0%；创建至分析保存 20.69s

[原始请求结果](/Users/shika/Documents/Support-Copilot/docs/verification/business-benchmark-2026-09-10/run-1/trials/c4-d2d-7eb233e7681db759178fbe3a2cbe8c60-2.json)

> I do not have sufficient verified evidence to answer this request. A support specialist needs to review it before any action or commitment.

### d2d-4dd9b7a0e747701ef73ba84052fe2701-2 · dmv

**问题：** What can I do if I forgot to update my address?

**发布者参考回复：** Don't forget to that, there are branches you can go to do this.

**发布者标注文档片段：**

> By statute , 
> you must report a change of address to DMV within ten days of moving. 
> That is the case for the address associated with your license, as well as all the addresses associated with each registered vehicle, which may differ. 

**并发 1：** live；无降级原因；参考文档命中 true；证据覆盖 100.0%；创建至分析保存 12.07s

[原始请求结果](/Users/shika/Documents/Support-Copilot/docs/verification/business-benchmark-2026-09-10/run-1/trials/c1-d2d-4dd9b7a0e747701ef73ba84052fe2701-2.json)

> Based on the archived information provided:
> 
> - For Social Security, sign in to or create a free my Social Security account, open **My Profile**, select **Update Contact Information**, enter the new address, choose when to schedule the update, review and verify the information, and select **Submit**. This online service is not available for people receiving SSI or those without a U.S. mailing address. For assistance, call 1-800-772-1213 or visit a Social Security office.
> - For DMV records, the archived guidance says a change of address must be reported within ten days of moving. Update the address associated with your license and each registered vehicle; notifying the Postal Service alone is not sufficient.
> 
> Please confirm whether you mean your Social Security or DMV address record so the appropriate process can be identified. This response is based on the supplied archived documents; current policy was not verified. [1][2]

**并发 2：** live；无降级原因；参考文档命中 true；证据覆盖 100.0%；创建至分析保存 10.63s

[原始请求结果](/Users/shika/Documents/Support-Copilot/docs/verification/business-benchmark-2026-09-10/run-1/trials/c2-d2d-4dd9b7a0e747701ef73ba84052fe2701-2.json)

> If you mean Social Security, sign in to or create a free my Social Security account, open My Profile, select Update Contact Information, enter your new address, choose when to schedule the update, review and verify the information, and submit it. This online service is unavailable to people receiving SSI or those without a U.S. mailing address; SSI recipients can check the address on record through My Profile. For help, call 1-800-772-1213 or contact a Social Security office.
> 
> If you mean New York DMV, the archived guidance says an address change should be reported within ten days of moving for both your license and each registered vehicle. Please specify which agency or account you need to update so the appropriate process can be confirmed. [1][2]

**并发 4：** live；无降级原因；参考文档命中 true；证据覆盖 100.0%；创建至分析保存 18.01s

[原始请求结果](/Users/shika/Documents/Support-Copilot/docs/verification/business-benchmark-2026-09-10/run-1/trials/c4-d2d-4dd9b7a0e747701ef73ba84052fe2701-2.json)

> If you forgot to update your address, update it as soon as possible with the relevant agency:
> 
> - For Social Security benefits: Sign in to your my Social Security account, open My Profile, select Update Contact Information, enter your address, choose when to schedule the update, review and verify the information, and select Submit. This online service is available for retirement, survivors, or disability benefits; it is not available for SSI recipients or people without a U.S. mailing address. For help, call 1-800-772-1213 or visit a Social Security office.
> - For DMV records: The archived guidance states that a change of address must be reported within ten days of moving for your license and each registered vehicle. Updating the address with the postal service alone is not sufficient.
> 
> Because the request does not identify the agency, use the applicable process above. This response is based on the supplied archived documents; current policy was not verified. [1][2]

### d2d-c4cf8c5c94690219e773e5c4aa9cd868-2 · ssa

**问题：** What are the next steps if I do not qualify for benefits on someone else's records?

**发布者参考回复：** Even when you do not qualify for benefits on someone else's record, we could use your record and maybe some members of your family may qualify this way.

**发布者标注文档片段：**

> Even if you do not qualify for benefits on someone else's record , 
> some members of your family may qualify for benefits on your record. 

**并发 1：** fallback；insufficient_evidence；参考文档命中 false；证据覆盖 0.0%；创建至分析保存 8.24s

[原始请求结果](/Users/shika/Documents/Support-Copilot/docs/verification/business-benchmark-2026-09-10/run-1/trials/c1-d2d-c4cf8c5c94690219e773e5c4aa9cd868-2.json)

> I do not have sufficient verified evidence to answer this request. A support specialist needs to review it before any action or commitment.

**并发 2：** fallback；insufficient_evidence；参考文档命中 false；证据覆盖 0.0%；创建至分析保存 8.23s

[原始请求结果](/Users/shika/Documents/Support-Copilot/docs/verification/business-benchmark-2026-09-10/run-1/trials/c2-d2d-c4cf8c5c94690219e773e5c4aa9cd868-2.json)

> I do not have sufficient verified evidence to answer this request. A support specialist needs to review it before any action or commitment.

**并发 4：** fallback；insufficient_evidence；参考文档命中 false；证据覆盖 0.0%；创建至分析保存 11.39s

[原始请求结果](/Users/shika/Documents/Support-Copilot/docs/verification/business-benchmark-2026-09-10/run-1/trials/c4-d2d-c4cf8c5c94690219e773e5c4aa9cd868-2.json)

> I do not have sufficient verified evidence to answer this request. A support specialist needs to review it before any action or commitment.

### d2d-d87fb09ad3610c92ffd649840b5a1d88-2 · ssa

**问题：** Hello, I'd like to know when a person is deemed disabled by your experts.

**发布者参考回复：** Yes, Disability Home.

**发布者标注文档片段：**

> Disability Home 

**并发 1：** live；无降级原因；参考文档命中 false；证据覆盖 0.0%；创建至分析保存 12.56s

[原始请求结果](/Users/shika/Documents/Support-Copilot/docs/verification/business-benchmark-2026-09-10/run-1/trials/c1-d2d-d87fb09ad3610c92ffd649840b5a1d88-2.json)

> According to the supplied archived Social Security Administration material, a person may be found disabled when their medical condition prevents basic work-related activities and is expected to last at least 12 months; the condition meets or equals a listed disabling condition; and the person cannot perform their past work or any other work, considering their medical condition, age, education, work experience, and transferable skills. If they can perform past or other work, the claim may not meet the qualifying disability standard. This answer is based on the supplied archive and does not verify current policy. [1]

**并发 2：** live；无降级原因；参考文档命中 false；证据覆盖 0.0%；创建至分析保存 8.83s

[原始请求结果](/Users/shika/Documents/Support-Copilot/docs/verification/business-benchmark-2026-09-10/run-1/trials/c2-d2d-d87fb09ad3610c92ffd649840b5a1d88-2.json)

> Based on the supplied archived Social Security Administration material, a person is deemed disabled when their medical condition significantly interferes with basic work-related activities for at least 12 months and, after the applicable evaluation steps, prevents them from performing their past work and any other work. If the condition meets or equals a listed disabling condition, the person may be found disabled at that stage. This answer is based on the archive provided; current policy was not verified. [1]

**并发 4：** fallback；structured_generation_response_timeout；参考文档命中 false；证据覆盖 0.0%；创建至分析保存 20.66s

[原始请求结果](/Users/shika/Documents/Support-Copilot/docs/verification/business-benchmark-2026-09-10/run-1/trials/c4-d2d-d87fb09ad3610c92ffd649840b5a1d88-2.json)

> I do not have sufficient verified evidence to answer this request. A support specialist needs to review it before any action or commitment.

### d2d-ca5e37399a52a168ddf7ae5360580f7f-2 · ssa

**问题：** Please tell me about the benefits for disabled people.

**发布者参考回复：** Sure, give me a moment.

**发布者标注文档片段：**

> Disability Home 

**并发 1：** fallback；structured_generation_response_timeout；参考文档命中 false；证据覆盖 0.0%；创建至分析保存 20.45s

[原始请求结果](/Users/shika/Documents/Support-Copilot/docs/verification/business-benchmark-2026-09-10/run-1/trials/c1-d2d-ca5e37399a52a168ddf7ae5360580f7f-2.json)

> I do not have sufficient verified evidence to answer this request. A support specialist needs to review it before any action or commitment.

**并发 2：** live；无降级原因；参考文档命中 false；证据覆盖 0.0%；创建至分析保存 9.39s

[原始请求结果](/Users/shika/Documents/Support-Copilot/docs/verification/business-benchmark-2026-09-10/run-1/trials/c2-d2d-ca5e37399a52a168ddf7ae5360580f7f-2.json)

> The archived information covers Social Security disability benefits, including disability evaluation criteria, benefits for children with disabilities, working while disabled, Medicare, receiving benefits by direct deposit, and a disability planner. For an application, the archive indicates that you may be asked for medical information—such as details about your conditions, doctors, medications, and tests—as well as work history and information about certain other benefits. It also lists possible eligibility documents, including proof of birth and proof of U.S. citizenship or lawful immigration status. This response is based only on the supplied archived documents; current eligibility rules and procedures were not verified. [1][2]

**并发 4：** live；无降级原因；参考文档命中 false；证据覆盖 0.0%；创建至分析保存 12.46s

[原始请求结果](/Users/shika/Documents/Support-Copilot/docs/verification/business-benchmark-2026-09-10/run-1/trials/c4-d2d-ca5e37399a52a168ddf7ae5360580f7f-2.json)

> The archived information covers Social Security disability benefits, including eligibility evaluation, benefits for children with disabilities, applying, receiving benefits, and working while disabled. An application may require detailed medical information—such as conditions, treating providers, medications, and medical tests—as well as work history and information about workers’ compensation or other disability-related benefits. Documents such as proof of birth and proof of U.S. citizenship or lawful status may also be requested. This response is based only on the supplied archive; current eligibility rules and procedures were not verified. [1][2]

### d2d-429aa5c591d70b7e4add35d9eced3ad3-2 · ssa

**问题：** I came here because I need to know if I should wait with my application for social security.

**发布者参考回复：** First of all, you should apply as soon as you become disabled.

**发布者标注文档片段：**

> You should apply as soon as you become disabled. 

**并发 1：** fallback；structured_generation_response_timeout；参考文档命中 false；证据覆盖 0.0%；创建至分析保存 20.86s

[原始请求结果](/Users/shika/Documents/Support-Copilot/docs/verification/business-benchmark-2026-09-10/run-1/trials/c1-d2d-429aa5c591d70b7e4add35d9eced3ad3-2.json)

> I do not have sufficient verified evidence to answer this request. A support specialist needs to review it before any action or commitment.

**并发 2：** live；无降级原因；参考文档命中 false；证据覆盖 0.0%；创建至分析保存 11.62s

[原始请求结果](/Users/shika/Documents/Support-Copilot/docs/verification/business-benchmark-2026-09-10/run-1/trials/c2-d2d-429aa5c591d70b7e4add35d9eced3ad3-2.json)

> The archived information does not say whether you should wait to apply or provide personalized advice about the best filing time. It states that you can submit an online application and receive a receipt and confirmation number. If benefits are scheduled more than two months in the future, application-status information will not be available until one month before benefits begin. After submission, Social Security reviews the application and contacts you if more information or documents are needed. This answer is based only on the supplied archive; current policy was not verified. [1]

**并发 4：** fallback；structured_generation_response_timeout；参考文档命中 false；证据覆盖 0.0%；创建至分析保存 20.68s

[原始请求结果](/Users/shika/Documents/Support-Copilot/docs/verification/business-benchmark-2026-09-10/run-1/trials/c4-d2d-429aa5c591d70b7e4add35d9eced3ad3-2.json)

> I do not have sufficient verified evidence to answer this request. A support specialist needs to review it before any action or commitment.

### d2d-0068f6d6076982dc04f6bd4fb9b07a39-2 · ssa

**问题：** I have some questions regarding my social security credits and could use some help with that.

**发布者参考回复：** Of course. You must earn at least 40 Social Security credits to qualify for Social Security benefits. You earn Social Security credits when you work and pay Social Security taxes.

**发布者标注文档片段：**

> You must earn at least 40 Social Security credits to qualify for Social Security benefits. 
> You earn Social Security credits when you work and pay Social Security taxes. 

**并发 1：** fallback；structured_generation_response_timeout；参考文档命中 true；证据覆盖 100.0%；创建至分析保存 20.86s

[原始请求结果](/Users/shika/Documents/Support-Copilot/docs/verification/business-benchmark-2026-09-10/run-1/trials/c1-d2d-0068f6d6076982dc04f6bd4fb9b07a39-2.json)

> I do not have sufficient verified evidence to answer this request. A support specialist needs to review it before any action or commitment.

**并发 2：** live；无降级原因；参考文档命中 true；证据覆盖 100.0%；创建至分析保存 9.29s

[原始请求结果](/Users/shika/Documents/Support-Copilot/docs/verification/business-benchmark-2026-09-10/run-1/trials/c2-d2d-0068f6d6076982dc04f6bd4fb9b07a39-2.json)

> According to the supplied archive, Social Security credits are earned through work and payment of Social Security taxes. You can earn up to four credits per year, and the earnings required for one credit may change each year. Credits determine eligibility, but having more than the minimum does not increase your benefit amount; benefit amounts are based on average earnings over your working years.
> 
> For retirement benefits, people born after 1928 generally need 40 credits. Disability eligibility also requires meeting recent-work and duration-of-work tests, with the recent-work requirement depending on age. Please specify whether your question concerns retirement, disability, or survivors benefits so we can address the relevant information from the archive. [1]

**并发 4：** fallback；structured_generation_response_timeout；参考文档命中 true；证据覆盖 100.0%；创建至分析保存 21.15s

[原始请求结果](/Users/shika/Documents/Support-Copilot/docs/verification/business-benchmark-2026-09-10/run-1/trials/c4-d2d-0068f6d6076982dc04f6bd4fb9b07a39-2.json)

> I do not have sufficient verified evidence to answer this request. A support specialist needs to review it before any action or commitment.

### d2d-617787216d04589888d3afdd75937f47-2 · ssa

**问题：** What are the original documents needed for getting an original social security card for a foreign-born U.S. citizen adopted child?.

**发布者参考回复：** The first thing you'll need to do is to prove your child's citizenship.

**发布者标注文档片段：**

> Citizenship 

**并发 1：** live；无降级原因；参考文档命中 true；证据覆盖 100.0%；创建至分析保存 16.67s

[原始请求结果](/Users/shika/Documents/Support-Copilot/docs/verification/business-benchmark-2026-09-10/run-1/trials/c1-d2d-617787216d04589888d3afdd75937f47-2.json)

> According to the supplied archived SSA document, you must present original documents or copies certified by the issuing agency. Photocopies, notarized copies, expired documents, and receipts showing that you applied for a document are not accepted.
> 
> For a foreign-born U.S. citizen adopted child, acceptable citizenship evidence includes one of the following:
> - Certificate of Citizenship (Form N-560 or N-561)
> - Certificate of Naturalization (Form N-550 or N-570)
> - U.S. passport
> - Machine Readable Immigrant Visa (MRIV) showing category code IR3 or IH3
> 
> For age evidence, provide the child’s foreign birth certificate if you have it or can obtain it within 10 days. If unavailable, the archive states that a child’s passport or a document issued by the Department of Homeland Security may be considered. A child age 12 or older requesting an original Social Security number must appear in person for an interview and provide evidence that the child does not already have a Social Security number.
> 
> This answer is based only on the supplied archived document; current requirements were not independently verified. [1]

**并发 2：** live；无降级原因；参考文档命中 true；证据覆盖 100.0%；创建至分析保存 15.22s

[原始请求结果](/Users/shika/Documents/Support-Copilot/docs/verification/business-benchmark-2026-09-10/run-1/trials/c2-d2d-617787216d04589888d3afdd75937f47-2.json)

> According to the supplied archived Social Security Administration information, you must present original documents or copies certified by the agency that issued them. Photocopies, notarized copies, expired documents, and receipts showing that you applied for a document are not accepted.
> 
> For a foreign-born U.S. citizen adopted child, acceptable proof of U.S. citizenship may include:
> - Certificate of Citizenship, Form N-560 or N-561
> - Certificate of Naturalization, Form N-550 or N-570
> - A Machine Readable Immigrant Visa showing category code IR3 or IH3
> - A U.S. passport
> 
> For proof of age, provide the child’s foreign birth certificate if you have it or can obtain it within 10 days. If unavailable, SSA may consider the child’s passport or a document issued by the Department of Homeland Security.
> 
> If the applicant is age 12 or older, the child must appear in person for an interview, and SSA will request evidence that the child has not previously been assigned a Social Security number. This answer is based on the supplied archived document; current requirements were not independently verified. [1]

**并发 4：** live；无降级原因；参考文档命中 true；证据覆盖 100.0%；创建至分析保存 12.69s

[原始请求结果](/Users/shika/Documents/Support-Copilot/docs/verification/business-benchmark-2026-09-10/run-1/trials/c4-d2d-617787216d04589888d3afdd75937f47-2.json)

> Based on the supplied archived SSA document, you must present original documents or copies certified by the agency that issued them. Photocopies, notarized copies, expired documents, and receipts showing that you applied for a document are not accepted.
> 
> For a foreign-born adopted child, acceptable proof of U.S. citizenship includes one of the following:
> - Certificate of Citizenship (Form N-560 or N-561)
> - Certificate of Naturalization (Form N-550 or N-570)
> - U.S. passport
> - Machine Readable Immigrant Visa (MRIV) showing category code IR3 or IH3
> 
> For proof of age, provide the child’s foreign birth certificate if available or obtainable within 10 days. If it is unavailable, the archived guidance says a passport or a document issued by the Department of Homeland Security may be considered.
> 
> If the child is age 12 or older and is applying for an original Social Security number, the child must appear in person for an interview, and evidence may be requested to show that the child has not previously been issued a Social Security number. [1]

### d2d-79b1344ed1f10ab9f9311f6865685ca9-2 · ssa

**问题：** HEllo. could you tell me what documents i need to get a card?

**发布者参考回复：** Hello, thanks for being patient, there are a few you may need To prove your child 's U.S. immigration status , you must show us your child 's current U.S. immigration document , such as : I-551 Lawful Permanent Resident Card , Machine Readable Immigrant Visa ;

**发布者标注文档片段：**

> Immigration Status 

**并发 1：** fallback；insufficient_evidence；参考文档命中 false；证据覆盖 0.0%；创建至分析保存 11.00s

[原始请求结果](/Users/shika/Documents/Support-Copilot/docs/verification/business-benchmark-2026-09-10/run-1/trials/c1-d2d-79b1344ed1f10ab9f9311f6865685ca9-2.json)

> I do not have sufficient verified evidence to answer this request. A support specialist needs to review it before any action or commitment.

**并发 2：** fallback；insufficient_evidence；参考文档命中 false；证据覆盖 0.0%；创建至分析保存 5.97s

[原始请求结果](/Users/shika/Documents/Support-Copilot/docs/verification/business-benchmark-2026-09-10/run-1/trials/c2-d2d-79b1344ed1f10ab9f9311f6865685ca9-2.json)

> I do not have sufficient verified evidence to answer this request. A support specialist needs to review it before any action or commitment.

**并发 4：** fallback；insufficient_evidence；参考文档命中 false；证据覆盖 0.0%；创建至分析保存 7.43s

[原始请求结果](/Users/shika/Documents/Support-Copilot/docs/verification/business-benchmark-2026-09-10/run-1/trials/c4-d2d-79b1344ed1f10ab9f9311f6865685ca9-2.json)

> I do not have sufficient verified evidence to answer this request. A support specialist needs to review it before any action or commitment.

### d2d-442d348541345791b53a6fa54c982be0-2 · ssa

**问题：** Will I still be able to continue with my eligibility for Disability benefits?

**发布者参考回复：** In most cases, you will continue to receive benefits as long as you are disabled.

**发布者标注文档片段：**

> In most cases , 
> you will continue to receive benefits as long as you are disabled. 
> However , 

**并发 1：** live；无降级原因；参考文档命中 true；证据覆盖 100.0%；创建至分析保存 17.45s

[原始请求结果](/Users/shika/Documents/Support-Copilot/docs/verification/business-benchmark-2026-09-10/run-1/trials/c1-d2d-442d348541345791b53a6fa54c982be0-2.json)

> According to the archived guidance, disability benefits generally continue as long as you remain disabled. Your case may be reviewed periodically, and eligibility can change if your medical condition improves or you return to work at a level considered substantial. You are responsible for promptly reporting any medical improvement or return to work. This response is based on the supplied archive and does not verify current policy or your individual benefit status. [1]

**并发 2：** live；无降级原因；参考文档命中 true；证据覆盖 100.0%；创建至分析保存 8.40s

[原始请求结果](/Users/shika/Documents/Support-Copilot/docs/verification/business-benchmark-2026-09-10/run-1/trials/c2-d2d-442d348541345791b53a6fa54c982be0-2.json)

> Based on the supplied archived information, you will generally continue to receive Disability benefits as long as you remain disabled. Social Security periodically reviews cases to verify continuing disability. Benefits may change or stop if your medical condition improves to the point that you are no longer considered disabled or if you work at a level considered substantial. You are responsible for promptly reporting any medical improvement or return to work. This response is based on the provided archive; current policy has not been independently verified. [1]

**并发 4：** live；无降级原因；参考文档命中 true；证据覆盖 100.0%；创建至分析保存 7.89s

[原始请求结果](/Users/shika/Documents/Support-Copilot/docs/verification/business-benchmark-2026-09-10/run-1/trials/c4-d2d-442d348541345791b53a6fa54c982be0-2.json)

> Based on the supplied archive, in most cases you can continue receiving disability benefits as long as you remain disabled. Your case may be reviewed periodically, and eligibility can change if your medical condition improves or you return to work at a substantial level. You are responsible for promptly reporting any improvement in your condition or return to work. Your individual eligibility and current status have not been verified here. [1]

### d2d-cd7374780cdf360d78bf672024c396a0-2 · studentaid

**问题：** Hello, I want information about the Extended Payment Plan

**发布者参考回复：** The first thing to know is that payments are made for up to 25 years.

**发布者标注文档片段：**

> Payments are made for up to 25 years. 

**并发 1：** live；无降级原因；参考文档命中 false；证据覆盖 0.0%；创建至分析保存 14.82s

[原始请求结果](/Users/shika/Documents/Support-Copilot/docs/verification/business-benchmark-2026-09-10/run-1/trials/c1-d2d-cd7374780cdf360d78bf672024c396a0-2.json)

> The supplied archive does not include specific details about the Extended Payment Plan, such as eligibility, terms, or payment amounts. You can use the Loan Simulator to explore repayment plans and compare estimated monthly payments. Please note that the simulator provides informational estimates and is not financial advice. This response is based on the archived documents and does not verify current policy. [1]

**并发 2：** live；无降级原因；参考文档命中 false；证据覆盖 0.0%；创建至分析保存 10.14s

[原始请求结果](/Users/shika/Documents/Support-Copilot/docs/verification/business-benchmark-2026-09-10/run-1/trials/c2-d2d-cd7374780cdf360d78bf672024c396a0-2.json)

> Based on the archived information available, the Loan Simulator can help you explore repayment plans and compare estimated monthly payments. It can also help assess options based on your needs and goals. The archive does not provide specific details about the Extended Payment Plan, and current policy has not been verified. [1]

**并发 4：** fallback；structured_generation_response_timeout；参考文档命中 false；证据覆盖 0.0%；创建至分析保存 20.93s

[原始请求结果](/Users/shika/Documents/Support-Copilot/docs/verification/business-benchmark-2026-09-10/run-1/trials/c4-d2d-cd7374780cdf360d78bf672024c396a0-2.json)

> I do not have sufficient verified evidence to answer this request. A support specialist needs to review it before any action or commitment.

### d2d-d9d85bc4227c2bac3a8de50ba1feadf5-2 · studentaid

**问题：** What can you tell me about Direct PLUS loans for parents?

**发布者参考回复：** Direct PLUS loans are for parents and can help pay for undergraudate students other expenses.

**发布者标注文档片段：**

> PLUS loans can help pay for education expenses not covered by other financial aid. 

**并发 1：** live；无降级原因；参考文档命中 true；证据覆盖 100.0%；创建至分析保存 15.86s

[原始请求结果](/Users/shika/Documents/Support-Copilot/docs/verification/business-benchmark-2026-09-10/run-1/trials/c1-d2d-d9d85bc4227c2bac3a8de50ba1feadf5-2.json)

> A Direct PLUS Loan for Parents is a federal loan that eligible parents can use to help pay education costs for a dependent undergraduate student at an eligible school. The loan can cover the school’s cost of attendance minus other financial assistance received by the student.
> 
> Generally, the borrower must be the student’s biological or adoptive parent, or in some cases a stepparent; the student must be enrolled at least half-time; and the borrower must meet federal student-aid eligibility requirements and not have an adverse credit history, unless additional requirements are met. Grandparents and legal guardians generally are not eligible unless they have legally adopted the student.
> 
> To apply, the student should first complete the FAFSA. Most schools use an online PLUS Loan application, although some have different processes. The school uses the application information to determine eligibility. Before receiving the loan, the parent must complete a Direct PLUS Loan Master Promissory Note. If a credit freeze is in place, it must be lifted at each credit bureau before applying.
> 
> You may request a deferment while the student is enrolled at least half-time and for an additional six months after the student graduates, leaves school, or drops below half-time enrollment. If you do not request a deferment, payments are expected after the loan is fully disbursed. Interest accrues during periods when payments are deferred, and your servicer will notify you when the first payment is due. If you have an adverse credit history, the archive says you may still qualify by obtaining an eligible endorser or meeting other applicable requirements.
> 
> The archived material lists a fixed 7.08% interest rate only for loans first disbursed from July 1, 2019, through June 30, 2020. This archive does not establish the current interest rate or current policy. [1][2][3]

**并发 2：** live；无降级原因；参考文档命中 true；证据覆盖 100.0%；创建至分析保存 18.39s

[原始请求结果](/Users/shika/Documents/Support-Copilot/docs/verification/business-benchmark-2026-09-10/run-1/trials/c2-d2d-d9d85bc4227c2bac3a8de50ba1feadf5-2.json)

> A Direct PLUS Loan for Parents is a federal loan that eligible parents can use to help pay education costs for a dependent undergraduate student enrolled at least half-time at an eligible school. The loan can cover the school’s cost of attendance minus other financial aid received by the student.
> 
> Generally, the borrower must be the student’s biological or adoptive parent—or, in some cases, stepparent—meet federal student-aid eligibility requirements, and not have an adverse credit history unless additional requirements are met. Grandparents and legal guardians generally are not eligible unless they have legally adopted the student.
> 
> To apply, the student should first complete the FAFSA. The parent then submits the PLUS application, following the school’s process, and must complete a Direct PLUS Loan Master Promissory Note before receiving the loan. The application may also allow the parent to request deferment and designate how a credit balance is paid. If a credit freeze is on the parent’s file, the archive states that it must be lifted at each credit bureau before the application can be processed.
> 
> The archived material states an interest rate of 7.08% for loans first disbursed from July 1, 2019, through June 30, 2020; this is historical information from the supplied archive, not a verification of the current rate. If a deferment is requested, payments generally are not required while the student is enrolled at least half-time and for an additional six months afterward, although interest continues to accrue. Without a deferment, payments are expected after the loan is fully disbursed. [1][2][3]

**并发 4：** live；无降级原因；参考文档命中 true；证据覆盖 100.0%；创建至分析保存 15.91s

[原始请求结果](/Users/shika/Documents/Support-Copilot/docs/verification/business-benchmark-2026-09-10/run-1/trials/c4-d2d-d9d85bc4227c2bac3a8de50ba1feadf5-2.json)

> A Direct PLUS Loan for parents is a federal loan for parents of dependent undergraduate students to help cover education costs not covered by other financial aid. The Department of Education provides these loans through participating schools.
> 
> Eligibility generally requires that you be the student’s biological or adoptive parent—or, in some cases, stepparent—that the student be enrolled at least half-time at an eligible school, that you do not have an adverse credit history unless you meet additional requirements, and that both you and the student meet federal student-aid eligibility requirements. Grandparents and legal guardians generally are not eligible unless they have legally adopted the student.
> 
> The parent typically applies through the online PLUS Loan application, although some schools use a different process. The student should complete the FAFSA first. Before receiving the loan, the parent must complete a Direct PLUS Loan Master Promissory Note. The application may also allow you to request deferment, designate who receives any credit balance, and authorize certain educational charges to be paid from loan funds. If your credit file has a security freeze, the archive says it must be lifted at each credit bureau before the application can be processed.
> 
> The maximum amount is generally the school’s cost of attendance minus other financial assistance received by the student. If you request deferment, payments generally are not required while the student is enrolled at least half-time and for an additional six months afterward; interest continues to accrue during deferment. The archived material lists a fixed 7.08% interest rate for loans first disbursed from July 1, 2019, through June 30, 2020. Because this is an archived document, that rate should not be treated as current policy. [1][2][3]

### d2d-aef95d3490b2ba529113aff97b0360e0-2 · studentaid

**问题：** I'm a student looking for help with preparing for college. Can you lend me a hand?

**发布者参考回复：** Of course. We've provided checklists with the steps you can take to help your or your child's chances of getting into and being able to afford the school of your choice.

**发布者标注文档片段：**

> We ve provided checklists with the steps you can take to help your or your child s chances of getting into and being able to afford the school of your choice. 

**并发 1：** live；无降级原因；参考文档命中 true；证据覆盖 100.0%；创建至分析保存 7.14s

[原始请求结果](/Users/shika/Documents/Support-Copilot/docs/verification/business-benchmark-2026-09-10/run-1/trials/c1-d2d-aef95d3490b2ba529113aff97b0360e0-2.json)

> Absolutely. The archived Federal Student Aid resources recommend preparing both academically and financially. Start with the checklist that matches your situation—for example, the high school, graduate school, adult student, or last-minute checklist. These cover academic preparation, time and money management, college savings, and financial-aid planning. The archive also includes a college-preparation video playlist for learning more about college life. [1][2]

**并发 2：** live；无降级原因；参考文档命中 true；证据覆盖 100.0%；创建至分析保存 11.41s

[原始请求结果](/Users/shika/Documents/Support-Copilot/docs/verification/business-benchmark-2026-09-10/run-1/trials/c2-d2d-aef95d3490b2ba529113aff97b0360e0-2.json)

> Absolutely. The archived Federal Student Aid resources recommend preparing both academically and financially. You can use checklists tailored to your stage, including high school grade-level, graduate school, adult student, and last-minute preparation checklists. They cover areas such as academic progress, time management, financial aid, and college savings. The archive also includes a college-preparation video playlist with introductory topics about college life. [1][2]

**并发 4：** live；无降级原因；参考文档命中 true；证据覆盖 100.0%；创建至分析保存 14.97s

[原始请求结果](/Users/shika/Documents/Support-Copilot/docs/verification/business-benchmark-2026-09-10/run-1/trials/c4-d2d-aef95d3490b2ba529113aff97b0360e0-2.json)

> Absolutely. The archived Federal Student Aid resources recommend using a college-preparation checklist covering both academic and financial readiness. Depending on your situation, you can review the high-school grade checklists, graduate-school checklist, adult-student checklist, or last-minute checklist. These resources include steps for preparing academically, learning about financial aid, managing time and money, and planning for college. Please note that this guidance comes from the supplied archive; current requirements and resources were not independently verified. [1][2]

### d2d-f4a55a931f23695ef29d9ff7d4abc800-2 · studentaid

**问题：** Hello, I wonder what is the Federal student loans for college?

**发布者参考回复：** You must request them and also pay them so you have to be sure.

**发布者标注文档片段：**

> You must repay your loan, so be sure you understand your options and responsibilities. 

**并发 1：** live；无降级原因；参考文档命中 true；证据覆盖 0.0%；创建至分析保存 8.45s

[原始请求结果](/Users/shika/Documents/Support-Copilot/docs/verification/business-benchmark-2026-09-10/run-1/trials/c1-d2d-f4a55a931f23695ef29d9ff7d4abc800-2.json)

> Federal student loans are loans that help students pay for college and must be repaid with interest. According to the supplied archive, they generally offer fixed and often lower interest rates than private loans, usually do not require a credit check or cosigner, and may allow repayment to begin after you leave college or drop below half-time enrollment. Depending on your circumstances, federal loans may also provide flexible repayment options, payment postponement, or potential forgiveness if specific conditions are met. Remember that borrowing creates a legal obligation, so consider how much you need and what you will be able to repay. [1]

**并发 2：** live；无降级原因；参考文档命中 true；证据覆盖 0.0%；创建至分析保存 8.63s

[原始请求结果](/Users/shika/Documents/Support-Copilot/docs/verification/business-benchmark-2026-09-10/run-1/trials/c2-d2d-f4a55a931f23695ef29d9ff7d4abc800-2.json)

> Federal student loans are loans from the federal government that help pay for college. Unlike grants, they must be repaid with interest. They generally offer fixed interest rates, often do not require a credit check or cosigner, and repayment usually begins after you leave college or drop below half-time enrollment. Some loans may offer interest benefits, flexible repayment plans, payment postponement options, or forgiveness eligibility if specific conditions are met. Before borrowing, consider how much you need and whether you will be able to repay it. This response is based on the supplied archived information; current terms and policies have not been verified. [1]

**并发 4：** live；无降级原因；参考文档命中 true；证据覆盖 0.0%；创建至分析保存 18.27s

[原始请求结果](/Users/shika/Documents/Support-Copilot/docs/verification/business-benchmark-2026-09-10/run-1/trials/c4-d2d-f4a55a931f23695ef29d9ff7d4abc800-2.json)

> Based on the supplied archived Federal Student Aid information, federal student loans are funds borrowed to help pay for college that must be repaid with interest. They generally offer a fixed interest rate, often lower than private-loan or credit-card rates, and most do not require a credit check or cosigner. Repayment typically begins after you leave college or drop below half-time enrollment. Depending on financial need and eligibility, some loans may receive interest benefits while you are in school, and flexible repayment options or forgiveness may be available under certain conditions. Remember that borrowing is a legal obligation, so consider how much you need and can afford to repay. [1]

### d2d-8f925a2c6bc41f8497c571d27d5bb470-2 · studentaid

**问题：** we might want to link your information on our site

**发布者参考回复：** That would be great, you can share our information with potential college students, their parents, counselors, or other mentors.

**发布者标注文档片段：**

> Share our information with potential college students, their parents, counselors, or other mentors. 

**并发 1：** fallback；structured_generation_response_timeout；参考文档命中 false；证据覆盖 0.0%；创建至分析保存 20.41s

[原始请求结果](/Users/shika/Documents/Support-Copilot/docs/verification/business-benchmark-2026-09-10/run-1/trials/c1-d2d-8f925a2c6bc41f8497c571d27d5bb470-2.json)

> I do not have sufficient verified evidence to answer this request. A support specialist needs to review it before any action or commitment.

**并发 2：** fallback；insufficient_evidence；参考文档命中 false；证据覆盖 0.0%；创建至分析保存 7.64s

[原始请求结果](/Users/shika/Documents/Support-Copilot/docs/verification/business-benchmark-2026-09-10/run-1/trials/c2-d2d-8f925a2c6bc41f8497c571d27d5bb470-2.json)

> I do not have sufficient verified evidence to answer this request. A support specialist needs to review it before any action or commitment.

**并发 4：** fallback；insufficient_evidence；参考文档命中 false；证据覆盖 0.0%；创建至分析保存 18.59s

[原始请求结果](/Users/shika/Documents/Support-Copilot/docs/verification/business-benchmark-2026-09-10/run-1/trials/c4-d2d-8f925a2c6bc41f8497c571d27d5bb470-2.json)

> I do not have sufficient verified evidence to answer this request. A support specialist needs to review it before any action or commitment.

### d2d-8c70d5a5f215350ddff51d41598c2320-2 · studentaid

**问题：** I need to correct my financial aid application and submit it right

**发布者参考回复：** Filling out and submitting your FAFSA form is an important step in the journey to paying for college

**发布者标注文档片段：**

> Filling out and submitting your FAFSA form is an important step in the journey to paying for college. 
> Learn about the next steps after submitting the application. 

**并发 1：** fallback；structured_generation_response_timeout；参考文档命中 true；证据覆盖 0.0%；创建至分析保存 20.86s

[原始请求结果](/Users/shika/Documents/Support-Copilot/docs/verification/business-benchmark-2026-09-10/run-1/trials/c1-d2d-8c70d5a5f215350ddff51d41598c2320-2.json)

> I do not have sufficient verified evidence to answer this request. A support specialist needs to review it before any action or commitment.

**并发 2：** live；无降级原因；参考文档命中 true；证据覆盖 0.0%；创建至分析保存 9.27s

[原始请求结果](/Users/shika/Documents/Support-Copilot/docs/verification/business-benchmark-2026-09-10/run-1/trials/c2-d2d-8c70d5a5f215350ddff51d41598c2320-2.json)

> You can correct mistakes on your FAFSA after it has been processed, either online or on paper. Online corrections require the student's FSA ID username and password; a parent cannot sign in to make changes. Before submitting, review the corrected information carefully. If the issue involves a changed financial situation rather than a mistake on the original form, contact the financial aid office at the school you plan to attend, since most information must reflect the situation on the date the FAFSA was signed. [1][2]

**并发 4：** live；无降级原因；参考文档命中 true；证据覆盖 0.0%；创建至分析保存 12.71s

[原始请求结果](/Users/shika/Documents/Support-Copilot/docs/verification/business-benchmark-2026-09-10/run-1/trials/c4-d2d-8c70d5a5f215350ddff51d41598c2320-2.json)

> If you made a mistake on your FAFSA application, you can correct it after the application has been processed. You may make the correction online or on paper. For an online correction, sign in with the student's FSA ID username and password; a parent cannot sign in to make changes to the form. Review the corrected information carefully before submitting it. This guidance comes from the supplied archived documents and has not been verified as current policy. [1][2]

### d2d-7b9641a604a8bfbf6f2f83a24392d8bc-2 · studentaid

**问题：** If I am not a US citizen, do I not qualify for federal student aid?

**发布者参考回复：** You should not assume that you cannot get help just because you are not a citizen.

**发布者标注文档片段：**

> Don t assume you can t get aid just because you re not a citizen. 

**并发 1：** live；无降级原因；参考文档命中 true；证据覆盖 100.0%；创建至分析保存 8.80s

[原始请求结果](/Users/shika/Documents/Support-Copilot/docs/verification/business-benchmark-2026-09-10/run-1/trials/c1-d2d-7b9641a604a8bfbf6f2f83a24392d8bc-2.json)

> No. Not being a U.S. citizen does not automatically disqualify you from federal student aid. Under the supplied archived guidance, eligible noncitizens—such as permanent residents and people in certain refugee, asylum, humanitarian, T-visa, or related statuses—may qualify if they meet the other eligibility requirements. Undocumented students, including DACA recipients, are not eligible for federal student aid, although they may qualify for state, college, or private aid. Check with your college or career school’s financial aid office to confirm which category applies to you and what documentation is required. [1][2][3]

**并发 2：** live；无降级原因；参考文档命中 true；证据覆盖 100.0%；创建至分析保存 8.71s

[原始请求结果](/Users/shika/Documents/Support-Copilot/docs/verification/business-benchmark-2026-09-10/run-1/trials/c2-d2d-7b9641a604a8bfbf6f2f83a24392d8bc-2.json)

> No. Not being a U.S. citizen does not automatically disqualify you from federal student aid. Many eligible noncitizens—including permanent residents and people in certain humanitarian or other qualifying immigration categories—may qualify if they meet the other eligibility requirements, such as financial need and enrollment in an eligible program. Undocumented students, including DACA recipients, are not eligible for federal student aid, though they may qualify for state, college, or private aid. Please check with your college or career school’s financial aid office to confirm your eligibility based on your immigration status. This answer is based on the supplied archived guidance; current policy was not independently verified. [1][2][3]

**并发 4：** live；无降级原因；参考文档命中 true；证据覆盖 100.0%；创建至分析保存 9.40s

[原始请求结果](/Users/shika/Documents/Support-Copilot/docs/verification/business-benchmark-2026-09-10/run-1/trials/c4-d2d-7b9641a604a8bfbf6f2f83a24392d8bc-2.json)

> Based on the supplied archived information, not being a U.S. citizen does not automatically disqualify you from federal student aid. Many eligible noncitizens—including permanent residents and certain refugees, asylees, parolees, T-visa holders, and other specified categories—may qualify if they meet the other eligibility requirements, such as financial need and enrollment in an eligible program. Undocumented students, including DACA recipients, are not eligible for federal student aid, though they may qualify for state, college, or private aid. Please check with your college or career school’s financial aid office to confirm which category applies to you and what documentation is required. [1][2][3]

### d2d-05282bcb9da1df86723f9aa17955c2af-2 · studentaid

**问题：** Hi, I have a Federal Family Education Loan and have heard that I might be eligible for a discharge of my loan. Is this right?

**发布者参考回复：** Yes this is correct you might be eligible if your college made a falsely certified your eligibility to receive a loan.

**发布者标注文档片段：**

> Learn more about false certification discharge to see whether you might qualify. 

**并发 1：** live；无降级原因；参考文档命中 true；证据覆盖 100.0%；创建至分析保存 11.81s

[原始请求结果](/Users/shika/Documents/Support-Copilot/docs/verification/business-benchmark-2026-09-10/run-1/trials/c1-d2d-05282bcb9da1df86723f9aa17955c2af-2.json)

> Based on the supplied archived information, an FFEL loan may qualify for discharge, but eligibility depends on the specific circumstances. The archive identifies potential eligibility for a closed-school discharge if the school closed while you were enrolled, while you were on an approved leave of absence, or within 120 days after you withdrew, subject to additional requirements. FFEL loans may also qualify for a false-certification discharge in circumstances such as unauthorized loan authorization or other qualifying false certification by the school.
> 
> The archive states that FFEL loans are not directly eligible for borrower-defense discharge. To seek that type of discharge for an FFEL loan, it says you would first need to consolidate it into a Direct Consolidation Loan and then contact the borrower-defense hotline.
> 
> For a closed-school discharge, contact your loan servicer about the application process and continue making payments while the application is being processed. This response is based on the supplied archive; current policy has not been independently verified. [1][2][3]

**并发 2：** live；无降级原因；参考文档命中 true；证据覆盖 100.0%；创建至分析保存 11.78s

[原始请求结果](/Users/shika/Documents/Support-Copilot/docs/verification/business-benchmark-2026-09-10/run-1/trials/c2-d2d-05282bcb9da1df86723f9aa17955c2af-2.json)

> Based on the archived guidance, an FFEL loan may qualify for discharge, but eligibility depends on the circumstances. For example, you may qualify for a closed-school discharge if your school closed while you were enrolled, while you were on an approved leave of absence, or within 120 days after you withdrew, subject to additional requirements. You may also qualify for a false-certification discharge in certain situations, such as unauthorized loan authorization or other qualifying school certification errors. Contact your loan servicer about the applicable application process, and continue making payments while an application is being processed. The archived guidance also states that FFEL loans are generally not eligible for borrower-defense discharge unless consolidated into a Direct Consolidation Loan. This archive does not establish that you personally qualify or verify current policy. [1][2][3]

**并发 4：** live；无降级原因；参考文档命中 true；证据覆盖 100.0%；创建至分析保存 16.94s

[原始请求结果](/Users/shika/Documents/Support-Copilot/docs/verification/business-benchmark-2026-09-10/run-1/trials/c4-d2d-05282bcb9da1df86723f9aa17955c2af-2.json)

> Yes, an FFEL loan may qualify for discharge, but eligibility depends on the specific circumstances—not solely on the loan being an FFEL loan. The archived information identifies possible pathways including:
> 
> - **Closed school discharge:** You may qualify if your school closed while you were enrolled, while you were on an approved leave of absence, or within 120 days after you withdrew, subject to additional requirements. You must apply through your loan servicer and continue making payments while the application is processed. [1]
> - **False certification discharge:** You may qualify if the school falsely certified your eligibility, such as through ability-to-benefit issues, a disqualifying status, or an unauthorized signature or payment. [2]
> - **Borrower defense:** FFEL loans are not eligible for discharge under borrower defense directly, but the archived information says they may become eligible after consolidation into a Direct Consolidation Loan. [3]
> 
> Contact your loan servicer to identify the applicable application and review your circumstances. This response is based on the supplied archived documents; current policy has not been independently verified. [1][2][3]

### d2d-0e17a4e9e0c8cd6ffc067cb77216f3db-2 · va

**问题：** What was the Orange Exposure Agent used for?

**发布者参考回复：** The United States Army used Agent Orange to clean plants and trees during the Vietnam War.

**发布者标注文档片段：**

> The U.S. military used Agent Orange to clear plants and trees during the Vietnam War. 

**并发 1：** live；无降级原因；参考文档命中 false；证据覆盖 0.0%；创建至分析保存 6.72s

[原始请求结果](/Users/shika/Documents/Support-Copilot/docs/verification/business-benchmark-2026-09-10/run-1/trials/c1-d2d-0e17a4e9e0c8cd6ffc067cb77216f3db-2.json)

> The Orange Exposure Agent refers to Agent Orange, a herbicide used by the U.S. military to clear trees and plants during the Vietnam War. The supplied archive also notes that C-123 aircraft were used to spray it. This answer is based on the archived documents provided; current policy was not verified. [1][2]

**并发 2：** live；无降级原因；参考文档命中 false；证据覆盖 0.0%；创建至分析保存 15.85s

[原始请求结果](/Users/shika/Documents/Support-Copilot/docs/verification/business-benchmark-2026-09-10/run-1/trials/c2-d2d-0e17a4e9e0c8cd6ffc067cb77216f3db-2.json)

> Agent Orange was a military herbicide used to clear trees and plants during the Vietnam War. [1][2]

**并发 4：** fallback；structured_generation_response_timeout；参考文档命中 false；证据覆盖 0.0%；创建至分析保存 20.63s

[原始请求结果](/Users/shika/Documents/Support-Copilot/docs/verification/business-benchmark-2026-09-10/run-1/trials/c4-d2d-0e17a4e9e0c8cd6ffc067cb77216f3db-2.json)

> I do not have sufficient verified evidence to answer this request. A support specialist needs to review it before any action or commitment.

### d2d-37973d2e5955b695cc7bee6cbc2f63bd-2 · va

**问题：** Enhanced eligibility for returning OEF/OIF/OND combat Veterans

**发布者参考回复：** You can receive free VA health care for up to 5 years after discharge or release for any condition related to your service in Operation Enduring Freedom OEF in Afghanistan or Operation Iraqi Freedom OIF or Operation New Dawn OND in Iraq .

**发布者标注文档片段：**

> You can receive free VA health care for up to 5 years after discharge or release for any condition related to your service in Operation Enduring Freedom OEF in Afghanistan or Operation Iraqi Freedom OIF or Operation New Dawn OND in Iraq. 
> This is called an enhanced eligibility period. 

**并发 1：** live；无降级原因；参考文档命中 true；证据覆盖 100.0%；创建至分析保存 10.39s

[原始请求结果](/Users/shika/Documents/Support-Copilot/docs/verification/business-benchmark-2026-09-10/run-1/trials/c1-d2d-37973d2e5955b695cc7bee6cbc2f63bd-2.json)

> Archived information states that returning OEF/OIF/OND combat Veterans may receive free VA health care for up to five years after discharge or release for conditions related to their service.
> 
> To qualify for enhanced eligibility, all of these must apply: you served in a combat theater after November 11, 1998; you were discharged or released from active service on or after January 29, 2003; and you did not receive a dishonorable discharge. Service may be verified with military documentation showing combat-theater service, combat-service medals, or qualifying combat-related pay documentation.
> 
> If you qualify, VA will enroll you right away and generally assign priority group 6 unless you qualify for a higher group based on income or a service-connected disability. The archive encourages eligible Veterans to apply promptly. This information is from the supplied archive; current policy has not been independently verified. [1]

**并发 2：** live；无降级原因；参考文档命中 true；证据覆盖 100.0%；创建至分析保存 18.42s

[原始请求结果](/Users/shika/Documents/Support-Copilot/docs/verification/business-benchmark-2026-09-10/run-1/trials/c2-d2d-37973d2e5955b695cc7bee6cbc2f63bd-2.json)

> The archived VA information states that returning OEF/OIF/OND combat Veterans may receive free VA health care for up to five years after discharge or release for conditions related to their service. All of these requirements must be met: service in a theater of combat operations after November 11, 1998; discharge or release from active service on or after January 29, 2003; and no dishonorable discharge. VA may use military service documentation, combat-service medals, or qualifying combat-related pay records to determine eligibility. Eligible Veterans are enrolled right away and assigned to priority group 6 unless they qualify for a higher priority group. This response is based on the supplied archived document; current policy was not independently verified. [1]

**并发 4：** fallback；structured_generation_response_timeout；参考文档命中 true；证据覆盖 100.0%；创建至分析保存 20.30s

[原始请求结果](/Users/shika/Documents/Support-Copilot/docs/verification/business-benchmark-2026-09-10/run-1/trials/c4-d2d-37973d2e5955b695cc7bee6cbc2f63bd-2.json)

> I do not have sufficient verified evidence to answer this request. A support specialist needs to review it before any action or commitment.

### d2d-b53f4c0d357f0bf1015b999151c620e7-2 · va

**问题：** I wanted to know if I can access substance use treatment if I don't have VA benefits

**发布者参考回复：** You might still be able to get care

**发布者标注文档片段：**

> You may still be able to get care : 

**并发 1：** live；无降级原因；参考文档命中 true；证据覆盖 100.0%；创建至分析保存 10.78s

[原始请求结果](/Users/shika/Documents/Support-Copilot/docs/verification/business-benchmark-2026-09-10/run-1/trials/c1-d2d-b53f4c0d357f0bf1015b999151c620e7-2.json)

> Yes. According to the supplied archived VA information, you may still be able to access substance use care even if you do not currently have VA health care benefits. If you served in a combat zone, you may be eligible for free private counseling, alcohol and drug assessment, and other support through a community Vet Center. You can also apply for VA health care; eligibility may depend on factors such as service history, disability, Medicaid eligibility, or household income. Contact a Vet Center or VA medical center to discuss your situation and confirm eligibility. This response is based on the supplied archived documents; current eligibility and availability have not been independently verified. [1][2]

**并发 2：** live；无降级原因；参考文档命中 true；证据覆盖 100.0%；创建至分析保存 12.59s

[原始请求结果](/Users/shika/Documents/Support-Copilot/docs/verification/business-benchmark-2026-09-10/run-1/trials/c2-d2d-b53f4c0d357f0bf1015b999151c620e7-2.json)

> Yes, you may still be able to access substance use support even if you do not currently have VA health care benefits. The archived VA information says that Veterans who served in a combat zone can receive free private counseling, alcohol and drug assessment, and other support through community Vet Centers. You can also apply for VA health care; eligibility may depend on factors such as service history, discharge circumstances, qualifying conditions, or income. Contact a Vet Center or VA medical center to verify which services and eligibility rules apply to you. This response is based on the supplied archived documents; current policy was not independently verified. [1][2]

**并发 4：** fallback；structured_generation_response_timeout；参考文档命中 true；证据覆盖 100.0%；创建至分析保存 20.26s

[原始请求结果](/Users/shika/Documents/Support-Copilot/docs/verification/business-benchmark-2026-09-10/run-1/trials/c4-d2d-b53f4c0d357f0bf1015b999151c620e7-2.json)

> I do not have sufficient verified evidence to answer this request. A support specialist needs to review it before any action or commitment.

### d2d-2e0a29b94fc37a6d9999bb17411d53df-2 · va

**问题：** hi i need more information about your medical benefits package

**发布者参考回复：** In our packages we cover preventive care services, such as:
  Health exams, including gender-specific exams
  Health education, including nutrition education

**发布者标注文档片段：**

> We cover preventive care services, like : 
> Health exams including gender - specific exams 
> Health education including nutrition education 

**并发 1：** fallback；insufficient_evidence；参考文档命中 false；证据覆盖 0.0%；创建至分析保存 9.13s

[原始请求结果](/Users/shika/Documents/Support-Copilot/docs/verification/business-benchmark-2026-09-10/run-1/trials/c1-d2d-2e0a29b94fc37a6d9999bb17411d53df-2.json)

> I do not have sufficient verified evidence to answer this request. A support specialist needs to review it before any action or commitment.

**并发 2：** fallback；insufficient_evidence；参考文档命中 false；证据覆盖 0.0%；创建至分析保存 6.55s

[原始请求结果](/Users/shika/Documents/Support-Copilot/docs/verification/business-benchmark-2026-09-10/run-1/trials/c2-d2d-2e0a29b94fc37a6d9999bb17411d53df-2.json)

> I do not have sufficient verified evidence to answer this request. A support specialist needs to review it before any action or commitment.

**并发 4：** fallback；insufficient_evidence；参考文档命中 false；证据覆盖 0.0%；创建至分析保存 7.13s

[原始请求结果](/Users/shika/Documents/Support-Copilot/docs/verification/business-benchmark-2026-09-10/run-1/trials/c4-d2d-2e0a29b94fc37a6d9999bb17411d53df-2.json)

> I do not have sufficient verified evidence to answer this request. A support specialist needs to review it before any action or commitment.

### d2d-2643f705477642cc5af4816396db86f1-2 · va

**问题：** I need more information about the deadline for my request, please.

**发布者参考回复：** Of course. As you might already know, submitting your request on time will ensure that you receive the maximum benefit if your case is granted. Please check the deadline for each review option and submit your request before that date.

**发布者标注文档片段：**

> Submitting your request on time will ensure that you receive the maximum benefit if your case is granted. 
> Please check the deadline for each review option and submit your request before that date. 

**并发 1：** fallback；insufficient_evidence；参考文档命中 false；证据覆盖 0.0%；创建至分析保存 6.26s

[原始请求结果](/Users/shika/Documents/Support-Copilot/docs/verification/business-benchmark-2026-09-10/run-1/trials/c1-d2d-2643f705477642cc5af4816396db86f1-2.json)

> I do not have sufficient verified evidence to answer this request. A support specialist needs to review it before any action or commitment.

**并发 2：** fallback；insufficient_evidence；参考文档命中 false；证据覆盖 0.0%；创建至分析保存 16.62s

[原始请求结果](/Users/shika/Documents/Support-Copilot/docs/verification/business-benchmark-2026-09-10/run-1/trials/c2-d2d-2643f705477642cc5af4816396db86f1-2.json)

> I do not have sufficient verified evidence to answer this request. A support specialist needs to review it before any action or commitment.

**并发 4：** fallback；structured_generation_response_timeout；参考文档命中 false；证据覆盖 0.0%；创建至分析保存 20.32s

[原始请求结果](/Users/shika/Documents/Support-Copilot/docs/verification/business-benchmark-2026-09-10/run-1/trials/c4-d2d-2643f705477642cc5af4816396db86f1-2.json)

> I do not have sufficient verified evidence to answer this request. A support specialist needs to review it before any action or commitment.

### d2d-f2c7263a9e752525322adf6d8df0d5d8-2 · va

**问题：** I need to get some information about VA Survivors Pension, please. 

**发布者参考回复：** VA Survivors Pension offers monthly payments to qualified surviving spouses and unmarried dependent children of wartime veterans who meet certain income and net worth limits set by Congress. 

**发布者标注文档片段：**

> A VA Survivors Pension offers monthly payments to qualified surviving spouses and unmarried dependent children of wartime Veterans who meet certain income and net worth limits set by Congress. 
> Find out if you qualify and how to apply. 

**并发 1：** live；无降级原因；参考文档命中 false；证据覆盖 0.0%；创建至分析保存 8.48s

[原始请求结果](/Users/shika/Documents/Support-Copilot/docs/verification/business-benchmark-2026-09-10/run-1/trials/c1-d2d-f2c7263a9e752525322adf6d8df0d5d8-2.json)

> Archived VA information indicates that VA Survivors Pension may be available to an eligible surviving spouse or child of a deceased Veteran with wartime service. The information includes resources to check eligibility, learn how to apply, and review Survivors Pension benefit rates. Current policy and eligibility requirements were not independently verified for this response. [1]

**并发 2：** live；无降级原因；参考文档命中 false；证据覆盖 0.0%；创建至分析保存 7.56s

[原始请求结果](/Users/shika/Documents/Support-Copilot/docs/verification/business-benchmark-2026-09-10/run-1/trials/c2-d2d-f2c7263a9e752525322adf6d8df0d5d8-2.json)

> The archived information indicates that VA Survivors Pension may be available to an eligible surviving spouse or child of a deceased Veteran with wartime service. The archive includes resources to check eligibility, learn how to apply, and review Survivors Pension benefit rates. This response is based on the supplied archived document; current VA policy has not been independently verified. [1]

**并发 4：** live；无降级原因；参考文档命中 false；证据覆盖 0.0%；创建至分析保存 9.28s

[原始请求结果](/Users/shika/Documents/Support-Copilot/docs/verification/business-benchmark-2026-09-10/run-1/trials/c4-d2d-f2c7263a9e752525322adf6d8df0d5d8-2.json)

> According to the supplied archived VA information, VA Survivors Pension may be available to an eligible surviving spouse or child of a deceased Veteran who had wartime service. The archive includes resources on eligibility and how to apply, as well as rates for surviving spouses and children. This response is based on the archived document; current VA policy and eligibility requirements have not been verified. [1]

### d2d-33c4e3b5cc259f86d82b3e84896c140d-2 · va

**问题：** can you tell me more about housing grants for veterans

**发布者参考回复：** We offer housing grants for Veterans and service members with certain service-connected disabilities so they can buy or change a home to meet their needs. Changing a home might involve installing ramps or widening doorways. You could be eligible for a disability housing grant and how to apply .

**发布者标注文档片段：**

> We offer housing grants for Veterans and service members with certain service - connected disabilities so they can buy or change a home to meet their needs and live more independently. 
> Changing a home might involve installing ramps or widening doorways. 
> Find out if you re eligible for a disability housing grant and how to apply. 

**并发 1：** live；无降级原因；参考文档命中 true；证据覆盖 100.0%；创建至分析保存 12.11s

[原始请求结果](/Users/shika/Documents/Support-Copilot/docs/verification/business-benchmark-2026-09-10/run-1/trials/c1-d2d-33c4e3b5cc259f86d82b3e84896c140d-2.json)

> VA offers disability housing grants to eligible Veterans and Servicemembers with certain service-connected disabilities. The grants may help buy, build, or modify a permanent home—for example, by installing ramps or widening doorways—to support independent living.
> 
> For a Specially Adapted Housing (SAH) grant, the archived guidance says you must own or plan to own the home and have a qualifying service-connected disability, such as loss or loss of use of limbs, blindness with loss or loss of use of a leg, certain severe burns, or qualifying lower-extremity loss affecting balance or walking. The archive lists up to three SAH grants and up to $85,645 for fiscal year 2019, but this is archived information and current amounts or eligibility rules have not been verified.
> 
> You can review eligibility and apply through the VA’s disability housing grant resources. The archive also lists the VA benefits hotline at 800-827-1000 for assistance. [1][2]

**并发 2：** live；无降级原因；参考文档命中 true；证据覆盖 100.0%；创建至分析保存 10.57s

[原始请求结果](/Users/shika/Documents/Support-Copilot/docs/verification/business-benchmark-2026-09-10/run-1/trials/c2-d2d-33c4e3b5cc259f86d82b3e84896c140d-2.json)

> The archived VA information describes disability housing grants for Veterans and Servicemembers with certain service-connected disabilities. These grants may help eligible applicants buy, build, or modify a permanent home—for example, by installing ramps or widening doorways—to support independent living.
> 
> For a Specially Adapted Housing (SAH) grant, the archive says you must own or plan to own the home and have a qualifying service-connected disability. Examples listed include loss or loss of use of limbs, certain severe burns, and qualifying blindness or lower-extremity conditions. The archive also describes a historical FY 2019 maximum of up to three grants totaling up to $85,645, subject to program limits.
> 
> You can review the VA’s disability housing grant application information and eligibility requirements. Because this response is based on archived documents, current eligibility, funding amounts, and program rules have not been verified. [1][2]

**并发 4：** fallback；structured_generation_response_timeout；参考文档命中 true；证据覆盖 100.0%；创建至分析保存 20.76s

[原始请求结果](/Users/shika/Documents/Support-Copilot/docs/verification/business-benchmark-2026-09-10/run-1/trials/c4-d2d-33c4e3b5cc259f86d82b3e84896c140d-2.json)

> I do not have sufficient verified evidence to answer this request. A support specialist needs to review it before any action or commitment.

### d2d-9859e8ddca9df71a96d767de05b4102d-2 · va

**问题：** Can you please explain what happens after a claim exam? I'm currently waiting for results, wondering about this.

**发布者参考回复：** Of course. After your VA claim exam, we'll review all the evidence in your file, assign your disability rating, and send you a decision notice a letter letting you know your disability rating.

**发布者标注文档片段：**

> We ll review all the evidence in your file, assign your disability rating, and send you a decision notice a letter letting you know your disability rating. 

**并发 1：** live；无降级原因；参考文档命中 true；证据覆盖 100.0%；创建至分析保存 10.26s

[原始请求结果](/Users/shika/Documents/Support-Copilot/docs/verification/business-benchmark-2026-09-10/run-1/trials/c1-d2d-9859e8ddca9df71a96d767de05b4102d-2.json)

> Based on the supplied archived information, after your VA claim exam, VA claims processors review the exam report and any ordered test results along with your medical records, military records, and statements related to the claim. VA then assigns a disability rating and sends you a decision notice explaining the rating.
> 
> The archive says processing commonly takes about 3 to 4 months from start to finish, although the time depends on the complexity of the claim and the number of conditions claimed. You can sign in to track your claim. To request a copy of the final exam report, contact your nearest VA regional benefit office or call 800-827-1000 to request an appointment to view your file. [1][2]

**并发 2：** live；无降级原因；参考文档命中 true；证据覆盖 100.0%；创建至分析保存 9.36s

[原始请求结果](/Users/shika/Documents/Support-Copilot/docs/verification/business-benchmark-2026-09-10/run-1/trials/c2-d2d-9859e8ddca9df71a96d767de05b4102d-2.json)

> According to the supplied archived information, after your VA claim exam, claims processors review the exam report, any ordered test results, medical and military records, and statements related to your claim. They then assign a disability rating and send you a decision notice explaining the result. You can sign in to track your claim. The archive says processing often takes about 3 to 4 months from start to finish, though timing depends on the complexity of the claim and the number of conditions claimed. To request a copy of the final exam report, contact your nearest VA regional benefit office or call 800-827-1000 to request an appointment to view your file. [1][2]

**并发 4：** live；无降级原因；参考文档命中 true；证据覆盖 100.0%；创建至分析保存 9.87s

[原始请求结果](/Users/shika/Documents/Support-Copilot/docs/verification/business-benchmark-2026-09-10/run-1/trials/c4-d2d-9859e8ddca9df71a96d767de05b4102d-2.json)

> According to the supplied archived information, after your VA claim exam, claims processors review the exam report, any ordered test results, and the other evidence in your file. VA then assigns a disability rating and sends you a decision notice explaining the rating. The archived information says processing commonly takes about 3–4 months from start to finish, but this is not a current status estimate or policy verification. You can contact your nearest VA regional benefit office or call 800-827-1000 to request a copy of the final exam report. [1]
