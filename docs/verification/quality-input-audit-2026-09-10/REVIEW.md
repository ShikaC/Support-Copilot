# 逐题输入与参考审计（AI 建议，全部待人工确认）

先审输入是否忠实、意图/缺失条件与参考是否成立，再决定是否运行。这里没有模型输出或回答质量成绩。原始准备记录的 DMV 路由错误已在 AMENDMENT-1.md 更正，以下是修正投影。

## qa-c133078c0b8c5805ef25afedc6cb96e9-5

**development · HUMAN_AUTHORED_DOCUMENT_DIALOGUE · CLARIFY · 候选纳入，待人工确认**

意图：急需在线支付驾驶民事罚款，询问所需材料

判断/修订原因：原问题未说明州别；发布者直接使用纽约身份信息。不能根据标注文档补出用户辖区。

**实际模型输入投影：**

```text
This evaluation uses historical archived documents, not verified current policy. Use only retrieved evidence. Previous agent messages are conversation context, not authoritative evidence.
Institution routing: DMV (state/jurisdiction not provided by routing)

user: Hello. I urgently need to know more about driver civil penalties. There is one I need to pay asap.
agent: Do you want to pay a driver civil penalty by mail for uninsured operation or uninsured accident?
user: No, not by mail. It needs to be faster than that.
user: What do I need to make a fast online payment?
```

来源：c133078c0b8c5805ef25afedc6cb96e9 / Pay driver civil penalty#1_0 / 目标 turn 5

发布者原参考：You must provide the last four digits of your Social Security Number, your DMV ID Number Client ID Number from your NY State driver license, learner permit or non-driver photo ID card see where to find information on your driver license.

缺失条件：罚款通知所属州/DMV

可接受补问示例：Which state's DMV issued the civil penalty?


禁止：假定纽约或弗吉尼亚；要求在客服对话直接发送 SSN；保证付款立即恢复驾驶资格

**AI 核对的原文依据：**

- span 8 [565, 765)：your driver license or driving privilege was suspended or revoked because you violated the NY State Zero Tolerance Law for drivers under age 21 see Penalties for alcohol or drug related offenses [3 ]
- span 18 [1252, 1293)：You can pay with a credit or debit card.
- span 19 [1293, 1349)：7 Your name and address on DMV records must be correct.
- span 22 [1430, 1482)：the last four digits of your Social Security Number
- span 23 [1482, 1554)：your DMV ID Number Client ID Number from your NY State driver license ,
- span 24 [1554, 1657)：learner permit or non - driver photo ID card see where to find information on your driver license [5],
- span 25 [1657, 1660)：or
- span 26 [1660, 1677)：your full name ,
- span 27 [1677, 1702)：date of birth and gender
- span 28 [1702, 1738)：If your driver license is revoked ,
- span 29 [1738, 1821)：your payment of the driver civil penalty does not restore your privilege to drive.
- span 30 [1821, 1971)：You must request and receive approval from DMV [6] to restore your license or driving privilege unless your revocation was for an uninsured accident.

人工状态：NOT_REVIEWED；请在独立审核文件中记录确认或修订，不能将本 AI 建议计为人工审核。

## qa-067a4198b35cc78ffa0ae0a30f9349dc-5

**holdout · HUMAN_AUTHORED_DOCUMENT_DIALOGUE · CLARIFY · 候选纳入，待人工确认**

意图：开设驾校并教授预许可课程，了解要求

判断/修订原因：用户已确认课程类型，但没有州别；1000 小时和场地细则属于纽约文档。

**实际模型输入投影：**

```text
This evaluation uses historical archived documents, not verified current policy. Use only retrieved evidence. Previous agent messages are conversation context, not authoritative evidence.
Institution routing: DMV (state/jurisdiction not provided by routing)

user: I'm thinking about opening a driving school and need information about the requirements to do so.
agent: The first thing you need to do before submitting an application is to receive approval from DMV for the use of the name for your driving school.
agent: Do you plan to teach the Pre-licensing course?
user: Yes, I will be.
```

来源：067a4198b35cc78ffa0ae0a30f9349dc / Open a driving school#3_0 / 目标 turn 5

发布者原参考：In that case, you will need to have a classroom that meets DMV's requirements. This means you'll need to have an experienced instructor who holds a valid instructor's card and has 1,000 hours or more of experience being a behind the wheel instructor. 

缺失条件：驾校拟开设的州/辖区

可接受补问示例：In which state will the driving school operate?


禁止：假定州别；把纽约课程/教练条件说成全国统一条件

**AI 核对的原文依据：**

- span 10 [558, 626)：authority to operate a business in New York State and this location
- span 20 [1086, 1141)：If your school will teach the Pre - licensing course ,
- span 21 [1141, 1243)：you must also have a classroom that meets DMV s requirements see also Request for Premises Check [3].
- span 22 [1243, 1401)：you must have an experienced instructor who holds a valid instructor s card, and has at least 1,000 hours of experience as a behind - the - wheel instructor.
- span 23 [1401, 1436)：you must keep appropriate records.
- span 24 [1436, 1575)：you must have a vehicle used for training and testing students that meets DMV s requirements see also List of Driving School Vehicles [4].

人工状态：NOT_REVIEWED；请在独立审核文件中记录确认或修订，不能将本 AI 建议计为人工审核。

## qa-a5d917071665232156177cb8c355d44e-4

**development · HUMAN_AUTHORED_DOCUMENT_DIALOGUE · CLARIFY · 候选纳入，待人工确认**

意图：纽约州内商业驾驶自我认证

判断/修订原因：州内驾驶不等于 non-excepted。发布者直接索要体检证明，遗漏 excepted/non-excepted 分支。

**实际模型输入投影：**

```text
This evaluation uses historical archived documents, not verified current policy. Use only retrieved evidence. Previous agent messages are conversation context, not authoritative evidence.
Institution routing: DMV (state/jurisdiction not provided by routing)

user: I want to self-certify
agent: What driving type will you be certifying
user: Just for here in New york
```

来源：a5d917071665232156177cb8c355d44e / Medical Certification FAQ's#3_0 / 目标 turn 4

发布者原参考：okay, we will need a copy of your USDOT Medical Examiners Certificate

缺失条件：实际驾驶用途是否属于 excepted operation

可接受补问示例：What type of commercial driving will you do, and is it an excepted operation?


禁止：仅因州内驾驶就判定必须提交体检证明；替用户推定豁免资格

**AI 核对的原文依据：**

- span 4 [220, 372)：Drivers that self - certify to a non - excepted driving type NA or NI are also required to submit a copy of their USDOT Medical Examiner s Certificate.
- span 10 [666, 697)：Non - Excepted Intrastate NA :
- span 11 [697, 765)：Commercial driving operation is restricted to New York State only ,
- span 12 [765, 827)：and you are required to meet the Federal medical requirements
- span 15 [998, 1023)：Excepted Intrastate EA :
- span 16 [1023, 1181)：Commercial driving operation is restricted to New York State, permitted for excepted operation only and you are exempt from the Federal medical requirements.
- span 50 [4194, 4316)：Federal regulations require all CDL drivers to certify to the type of driving in which they operate or expect to operate.
- span 51 [4316, 4417)：You should choose the box which describes the type of driving that you perform or expect to perform.
- span 52 [4417, 4534)：If you expect to operate in an excepted driving type EA or EI then a Medical Examiner s Certificate is not required.
- span 54 [4629, 4747)：If you expect to operate in a non - excepted driving type NA or NI then a Medical Examiner s Certificate is required.

人工状态：NOT_REVIEWED；请在独立审核文件中记录确认或修订，不能将本 AI 建议计为人工审核。

## qa-b180df810bdee917ef43765903680cb8-4

**holdout · HUMAN_AUTHORED_DOCUMENT_DIALOGUE · CLARIFY · 候选纳入，待人工确认**

意图：获取本人的 CDL 驾驶记录，用户不需要定义解释

判断/修订原因：首轮问题仍未解决，末尾 not 是拒绝解释定义，不是无业务意图；需要州别后确定适用获取方式。发布者只给 MyDMV 标题，不能当完整步骤。

**实际模型输入投影：**

```text
This evaluation uses historical archived documents, not verified current policy. Use only retrieved evidence. Previous agent messages are conversation context, not authoritative evidence.
Institution routing: DMV (state/jurisdiction not provided by routing)

user: how do i get my own CDL driving record
agent: Want to know what is a CDL Driving Record Summary?
user: not
```

来源：b180df810bdee917ef43765903680cb8 / Get my own CDL driving record (abstract)#1_0 / 目标 turn 4

发布者原参考：you want to know how to connect through MyDMV

缺失条件：CDL 由哪个州签发

可接受补问示例：Which state issued your CDL?


禁止：将 not 作为纯寒暄删题；把纽约费用/门户当成所有州通用

**AI 核对的原文依据：**

- span 6 [420, 556)：Employers or organizations can get CDL Abstracts for enrolled drivers through the New York DMV License Event Notification Service LENS.
- span 10 [789, 817)：Get online through MyDMV
- span 11 [817, 870)：You can save and print a PDF version of your record.
- span 16 [987, 1042)：a New York State license, permit or non - driver ID or
- span 23 [1250, 1472)：you can mail a Request for Certified CDL Abstract PDF [5] MV - CDL form along with the $10 fee to the DMV to the address provided on the form, or have your employer order your CDL driving record abstract through LENS [6].

人工状态：NOT_REVIEWED；请在独立审核文件中记录确认或修订，不能将本 AI 建议计为人工审核。

## qa-a508b35d83b70e7ddfa5d2355542b18a-4

**development · HUMAN_AUTHORED_DOCUMENT_DIALOGUE · CLARIFY · 候选纳入，待人工确认**

意图：了解 IRP 注册可做哪些变更

判断/修订原因：确认想听常见变更并非无意义确认；但来源含 NY 特定注册操作，适用辖区缺失。可先给条件性概览并确认注册州，不要求先报具体车辆信息。

**实际模型输入投影：**

```text
This evaluation uses historical archived documents, not verified current policy. Use only retrieved evidence. Previous agent messages are conversation context, not authoritative evidence.
Institution routing: DMV (state/jurisdiction not provided by routing)

user: Hello there. How are you doing? I have some questions about making changes to an IRP registration.
agent: Would you like to know what common changes you can make to IRP registrations?
user: Sure, why not?
```

来源：a508b35d83b70e7ddfa5d2355542b18a / Changes to IRP registration#1_0 / 目标 turn 4

发布者原参考：You can add or delete vehicles, transfer plates from one vehicle to another or add jurisdictions, for example.

缺失条件：IRP 注册的基准州/辖区

可接受补问示例：Which jurisdiction is your IRP registration based in?


禁止：直接套用纽约材料和费用；假定用户已经选择某一种变更

**AI 核对的原文依据：**

- span 2 [34, 81)：Common changes to IRP registrations include
- span 3 [81, 104)：add or delete vehicles
- span 4 [104, 148)：transfer plates from one vehicle to another
- span 5 [148, 166)：add jurisdictions
- span 6 [166, 205)：increase or decrease registered weight
- span 7 [205, 256)：transfer a vehicle from one fleet to another fleet
- span 8 [256, 268)：name change
- span 9 [268, 285)：address change 1
- span 14 [532, 702)：provide proof of NY State insurance NY State Insurance ID Card in same name as the registrant if you are adding vehicles to the fleet submit for all changes listed above
- span 15 [702, 825)：provide proof of NY State insurance NY State Insurance ID Card in the new name if you are changing the name on the account

人工状态：NOT_REVIEWED；请在独立审核文件中记录确认或修订，不能将本 AI 建议计为人工审核。

## qa-cb9fe9549014af6ff319d5a08bb5eb68-5

**holdout · HUMAN_AUTHORED_DOCUMENT_DIALOGUE · CLARIFY · 候选纳入，待人工确认**

意图：注册 MyDMV 账号

判断/修订原因：产品名存在但路由未提供州别；初版错误 Virginia 必须移除。暂保守标为补问，人工确认是否 MyDMV 足以唯一定位纽约；若确认可答需新标签版本，不静默改标。

**实际模型输入投影：**

```text
This evaluation uses historical archived documents, not verified current policy. Use only retrieved evidence. Previous agent messages are conversation context, not authoritative evidence.
Institution routing: DMV (state/jurisdiction not provided by routing)

user: what do we us a mydmv account for?
agent: Okay, a MyDMV web account provides registered Users with secure and simplified access to use a variety of DMV’s on-line applications and services.
agent: Would you like to register for an account?
user: yes, what do I do
```

来源：cb9fe9549014af6ff319d5a08bb5eb68 / MyDMV Account Terms of Service#1_0 / 目标 turn 5

发布者原参考：After you register for an account you will be sent a temporary password by email. You will need the temporary password to complete the on-line registration process.  

缺失条件：是否纽约州 MyDMV

可接受补问示例：Do you mean the New York State MyDMV service?


禁止：把州别当作用户已提供；把临时密码片段当成完整注册步骤

**AI 核对的原文依据：**

- span 4 [187, 337)：was created by the New York State Department of Motor Vehicles DMV, in cooperation with the New York State Office of Information Technology Services.
- span 5 [337, 374)：In order to register for a account ,
- span 6 [374, 469)：you must first select a Sign - In Username and Password and provide your identity information.
- span 7 [469, 652)：Your Username, Password, and identity information are stored in a secure directory called the NY.gov, which is maintained by New York State Office of Information Technology Services.
- span 9 [674, 708)：When you register for a account ,
- span 10 [708, 756)：you will be sent a temporary password by email.
- span 11 [756, 840)：You must use the temporary password to complete the on - line registration process.
- span 13 [877, 985)：you can use your permanent Sign - In Username and Password for gaining access to applications and services.

人工状态：NOT_REVIEWED；请在独立审核文件中记录确认或修订，不能将本 AI 建议计为人工审核。

## qa-a9212f7fd13c01dd2792c745528ce33c-4

**development · HUMAN_AUTHORED_DOCUMENT_DIALOGUE · DIRECT · 候选纳入，待人工确认**

意图：了解 SSA 在线身份验证如何保护信息

判断/修订原因：用户拒绝故障排查但仍想了解验证安全；发布者转问是否愿意开户偏离意图。用原文验证流程替换该参考。

**实际模型输入投影：**

```text
This evaluation uses historical archived documents, not verified current policy. Use only retrieved evidence. Previous agent messages are conversation context, not authoritative evidence.
Institution routing: US Social Security Administration

user: I want to know if my information is secure.
agent: Are you having trouble with  the Online Identity Verification Process?
user: No, I just want to know more about it.
```

来源：a9212f7fd13c01dd2792c745528ce33c / my Social Security | Security and Protection | Social Security Administration#1_0 / 目标 turn 4

发布者原参考：Do you not want to create an account online?

缺失条件：无预设缺失条件

可接受补问示例：不适用

- 必要要点：以用户名/密码加第二验证方式保护登录（跨度 10, 15, 16）
- 必要要点：第二步输入短信或邮箱发送的安全码，方式由用户选择（跨度 19, 20, 21）

禁止：保证绝不会泄露；继续假定用户拒绝开户；要求用户把密码或验证码发给客服

**AI 核对的原文依据：**

- span 6 [322, 506)：Our security process follows federal guidelines that includes additional security measures so we can be sure that you are who you say you are when you conduct online business with us.
- span 10 [637, 692)：Requires you to sign in with a username and password ;
- span 15 [821, 969)：you can choose either your cell phone or email address as your second identification method when you sign in to or register for my Social Security.
- span 16 [969, 1103)：Two forms of identification when signing in will help better protect your account from unauthorized use and potential identity fraud.
- span 19 [1173, 1207)：Enter your username and password.
- span 20 [1207, 1266)：Enter the security code we send by text message or email ,
- span 21 [1266, 1350)：depending on your choice cell phone provider text message and data rates may apply.

人工状态：NOT_REVIEWED；请在独立审核文件中记录确认或修订，不能将本 AI 建议计为人工审核。

## qa-5de9a253ebae7cda68b7c7aa70fc721c-4

**holdout · HUMAN_AUTHORED_DOCUMENT_DIALOGUE · DIRECT · 候选纳入，待人工确认**

意图：询问退休福利是否支持在线申请

判断/修订原因：这是申请渠道的一般问题，不是要求判定本人资格。发布者 yes 遗漏某些条件和账号步骤，补齐条件限定即可，不必强求个人年龄。

**实际模型输入投影：**

```text
This evaluation uses historical archived documents, not verified current policy. Use only retrieved evidence. Previous agent messages are conversation context, not authoritative evidence.
Institution routing: US Social Security Administration

user: can I apply online for benefits?
agent: Did you want to apply for retirement benefits, disability benefits, or Medicare?
user: retirement benefits
```

来源：5de9a253ebae7cda68b7c7aa70fc721c / Benefits Planner | Social Security Administration#2_0 / 目标 turn 4

发布者原参考：Yes, you can complete your application online 

缺失条件：无预设缺失条件

可接受补问示例：不适用

- 必要要点：符合条件的退休福利申请可在线完成，不保证本人已符合资格（跨度 9, 10）
- 必要要点：需同意服务条款并创建或登录 my Social Security；若无法处理会收到电话/预约指引（跨度 11, 12, 13）

禁止：保证用户符合资格或获批；忽略在线申请的条件限制

**AI 核对的原文依据：**

- span 9 [415, 531)：If you want to apply for retirement benefits, disability benefits, or just Medicare and you meet certain criteria ,
- span 10 [531, 573)：you can complete your application online.
- span 11 [573, 698)：You will be asked to agree to a Terms of Service Agreement and create or log in to your personal my Social Security account.
- span 12 [698, 743)：If we are not able to process your request ,
- span 13 [743, 839)：you will receive specific information on how to contact us by phone or schedule an appointment.

人工状态：NOT_REVIEWED；请在独立审核文件中记录确认或修订，不能将本 AI 建议计为人工审核。

## qa-80be4b895fd193b2e3867ef01e9cd0cd-4

**development · HUMAN_AUTHORED_DOCUMENT_DIALOGUE · CLARIFY · 候选纳入，待人工确认**

意图：更改 SSA 地址与电话

判断/修订原因：原参考只给前两步并预设福利类型；原文对 SSI 与无美国邮寄地址有例外。先确认适用渠道或给出条件分支。

**实际模型输入投影：**

```text
This evaluation uses historical archived documents, not verified current policy. Use only retrieved evidence. Previous agent messages are conversation context, not authoritative evidence.
Institution routing: US Social Security Administration

user: If I needed to change my address and phone number where do i begin?
agent: So you want to change your address correct?
user: yes
```

来源：80be4b895fd193b2e3867ef01e9cd0cd / Change of Address| Social Security Administration#2_0 / 目标 turn 4

发布者原参考： If you get Social Security benefits retirement , survivors , or disability , [6] you can update your contact information in a safe , quick , and convenient way by following these five steps

缺失条件：领取的是退休/遗属/残障福利还是 SSI；是否有美国邮寄地址

可接受补问示例：Which benefit do you receive, and do you have a US mailing address?


禁止：向 SSI 用户保证可在线完成变更；让用户在对话内提供完整地址

**AI 核对的原文依据：**

- span 5 [321, 396)：If you get Social Security benefits retirement, survivors, or disability ,
- span 6 [396, 505)：you can update your contact information in a safe, quick, and convenient way by following these five steps :
- span 7 [505, 535)：Log in to my Social Security.
- span 8 [535, 595)：Select the My Profile link on the right side of the screen.
- span 9 [595, 676)：Select the Update Contact Information button and enter your address information.
- span 10 [676, 745)：Select when would you like to schedule the update, then select Next.
- span 11 [745, 782)：Review and verify your information ,
- span 12 [782, 797)：select Submit.
- span 13 [797, 931)：This service is not currently available to people who receive Supplemental Security Income SSI or do not have a U.S. mailing address.
- span 15 [941, 968)：if you are receiving SSI ,
- span 16 [968, 1066)：you can easily check your address we have on record via the My Profile Tab on my Social Security.
- span 23 [1517, 1623)：If you have questions or need help understanding how to change your address and telephone number online ,
- span 24 [1623, 1712)：call our toll - free number a 1 - 800 - 772 - 1213 or visit your Social Security office.

人工状态：NOT_REVIEWED；请在独立审核文件中记录确认或修订，不能将本 AI 建议计为人工审核。

## qa-6d5cff9a1b76423262f0b4f4b0f19ab9-4

**holdout · HUMAN_AUTHORED_DOCUMENT_DIALOGUE · CLARIFY · 候选纳入，待人工确认**

意图：为本人选择何时开始退休福利

判断/修订原因：快到退休年龄不足以个性化选择；发布者 50–60 岁问题是任意窄化。原文说没有通用最佳年龄，应了解个人与家庭情况。

**实际模型输入投影：**

```text
This evaluation uses historical archived documents, not verified current policy. Use only retrieved evidence. Previous agent messages are conversation context, not authoritative evidence.
Institution routing: US Social Security Administration

user: When is a good time to use the Benefits Planner?
agent: What is your age?
user: I am close to retirement age and was wondering when would be the best time to start my benefits.
```

来源：6d5cff9a1b76423262f0b4f4b0f19ab9 / Benefits Planner: Retirement | Other Things to Consider | Social Security Administration#1_0 / 目标 turn 4

发布者原参考：Is your age between the 50 and 60 range?

缺失条件：实际年龄/计划开始时间；是否继续工作及本人关注的收入需要

可接受补问示例：What is your age, and do you plan to keep working when you start benefits?


禁止：推荐一个对所有人最佳的领取年龄；把年龄猜成 50–60 岁；承诺终身收益最大化

**AI 核对的原文依据：**

- span 4 [105, 202)：The answer is that there is no one " best age " for everyone and, ultimately, it is your choice.
- span 5 [202, 323)：You should make an informed decision about when to apply for benefits based on your individual and family circumstances.
- span 6 [323, 428)：Your monthly benefit amount can differ substantially based on the age when you start receiving benefits.
- span 8 [462, 496)：before your full retirement age ,
- span 9 [496, 578)：your benefit will be smaller but you will receive it for a longer period of time.
- span 10 [578, 617)：at your full retirement age or later ,
- span 11 [617, 689)：you will receive a larger monthly benefit for a shorter period of time.
- span 14 [882, 916)：If you plan to continue working ,
- span 15 [916, 1040)：there are limits on how much you can earn each year between age 62 and full retirement age and still get all your benefits.
- span 18 [1160, 1192)：If your earnings will be high ,
- span 19 [1192, 1265)：you may decide to wait until full retirement age to start your benefits.

人工状态：NOT_REVIEWED；请在独立审核文件中记录确认或修订，不能将本 AI 建议计为人工审核。

## qa-ee3183f59b6c07856fb19dfbf9684665-5

**development · HUMAN_AUTHORED_DOCUMENT_DIALOGUE · DIRECT · 候选纳入，待人工确认**

意图：了解离婚对退休福利条件的影响

判断/修订原因：一般条件问题，可完整解释前配偶记录福利的条件，不推定个人资格。发布者只标注结果，补足全部前提。

**实际模型输入投影：**

```text
This evaluation uses historical archived documents, not verified current policy. Use only retrieved evidence. Previous agent messages are conversation context, not authoritative evidence.
Institution routing: US Social Security Administration

user: hello, how are you? I would like information of retirement benefits please?
agent: Are you married?
user: No  Iam not married
user: What if I am divorced?
```

来源：ee3183f59b6c07856fb19dfbf9684665 / Benefits Planner: Retirement | If You Are Divorced | Social Security Administration#1_0 / 目标 turn 5

发布者原参考：If you are divorced , but your marriage lasted 10 years or longer , you can receive benefits on your ex - spouse 's record even if they have remarried if 

缺失条件：无预设缺失条件

可接受补问示例：不适用

- 必要要点：前段婚姻至少10年、目前未婚、至少62岁、前配偶具有退休/残障福利资格（跨度 3, 5, 6, 7）
- 必要要点：本人工作记录对应福利低于前配偶记录福利；再婚通常影响此权利，不能保证获批（跨度 9, 10, 11）

禁止：仅凭离婚即保证获得福利；把前配偶再婚误说成禁止领取；省略婚龄/年龄条件

**AI 核对的原文依据：**

- span 3 [55, 122)：If you are divorced, but your marriage lasted 10 years or longer ,
- span 4 [122, 209)：you can receive benefits on your ex - spouse's record even if they have remarried if :
- span 5 [209, 229)：You are unmarried ;
- span 6 [229, 255)：You are age 62 or older ;
- span 7 [255, 339)：Your ex - spouse is entitled to Social Security retirement or disability benefits ;
- span 9 [343, 483)：The benefit you are entitled to receive based on your own work is less than the benefit you would receive based on your ex - spouse's work.
- span 10 [483, 500)：If you remarry ,
- span 11 [500, 642)：you generally cannot collect benefits on your former spouse's record unless your later marriage ends whether by death, divorce, or annulment.
- span 12 [642, 820)：If your ex - spouse has not applied for retirement benefits, but can qualify for them, you can receive benefits on their record if you have been divorced for at least two years.

人工状态：NOT_REVIEWED；请在独立审核文件中记录确认或修订，不能将本 AI 建议计为人工审核。

## qa-e10f962a370d0a7169a72159b4c1229f-4

**holdout · HUMAN_AUTHORED_DOCUMENT_DIALOGUE · CLARIFY · 候选纳入，待人工确认**

意图：判断本人某种生活变化是否应通知 SSA

判断/修订原因：用户只说发生了变化，无法判断其是否影响福利；需变化类别，允许先说明与福利相关的变化应报告。

**实际模型输入投影：**

```text
This evaluation uses historical archived documents, not verified current policy. Use only retrieved evidence. Previous agent messages are conversation context, not authoritative evidence.
Institution routing: US Social Security Administration

user: Hello there. I need to know if I should inform you of any changes in my life. My neighbour said I should, but I don't know anything about this.
agent: Has a change happened in your life?
user: Yes, there has been a change.
```

来源：e10f962a370d0a7169a72159b4c1229f / Manage Your Retirement Benefits | SSA#1_0 / 目标 turn 4

发布者原参考：In that case letting us know ensures your benefits and information is kept up to date. Remember to tell us whenever there s a change in your life circumstance that could affect your benefits.

缺失条件：发生的是哪一类生活变化

可接受补问示例：What kind of change occurred, such as moving or a change in marital status?


禁止：假定任意变化一定影响福利；要求无关敏感原文

**AI 核对的原文依据：**

- span 32 [2161, 2235)：letting us know ensures your benefits and information is kept up to date.
- span 33 [2235, 2340)：Remember to tell us whenever there s a change in your life circumstance that could affect your benefits.
- span 34 [2340, 2373)：Common changes to notify us of :
- span 35 [2373, 2381)：Moving.
- span 36 [2381, 2410)：Getting married or divorced.
- span 37 [2410, 2430)：Changing your name.
- span 38 [2430, 2448)：Adopting a child.
- span 39 [2448, 2500)：No longer caring for a child who receives benefits.
- span 47 [2760, 2810)：If you already receive Social Security benefits ,
- span 48 [2810, 2904)：you can update much of your information online with your personal my Social Security account.
- span 49 [2904, 2982)：If you need to make a change that cannot be done through my Social Security ,
- span 50 [2982, 3025)：you can contact us for additional support.

人工状态：NOT_REVIEWED；请在独立审核文件中记录确认或修订，不能将本 AI 建议计为人工审核。

## qa-6dc95d6948e2ade445cac0a7cca977b0-4

**development · HUMAN_AUTHORED_DOCUMENT_DIALOGUE · DIRECT · 候选纳入，待人工确认**

意图：现有 IDR 计划年度收入重新认证

判断/修订原因：前文已经确认 annual recertification，不可只把末尾 Yes 当作无业务意图。目标参考与原文相符。

**实际模型输入投影：**

```text
This evaluation uses historical archived documents, not verified current policy. Use only retrieved evidence. Previous agent messages are conversation context, not authoritative evidence.
Institution routing: US Federal Student Aid

user: Hello i would like to get information about Recurring IDR Requesters
agent: Do you want to file an annual recertification of your income?
user: Yes
```

来源：6dc95d6948e2ade445cac0a7cca977b0 / Apply for Income-Driven Student Loan Repayment | Federal Student Aid#1_0 / 目标 turn 4

发布者原参考：To recertify your current income-based payment plan, you must provide updated information about your income and family size annually.

缺失条件：无预设缺失条件

可接受补问示例：不适用

- 必要要点：每年提供更新的收入和家庭人数信息以重新认证现有收入驱动还款计划（跨度 25）

禁止：改成首次申请或切换计划；保证降低月供；把历史流程作为现行政策保证

**AI 核对的原文依据：**

- span 24 [1272, 1319)：Submit annual re-certification of my income
- span 25 [1319, 1465)：To re - certify for your existing income - driven repayment plan you must provide updated information about your income and family size annually.
- span 26 [1465, 1481)：LOG IN TO START

人工状态：NOT_REVIEWED；请在独立审核文件中记录确认或修订，不能将本 AI 建议计为人工审核。

## qa-4dd1dc4547298b8efc730bb4fbccda6f-4

**holdout · HUMAN_AUTHORED_DOCUMENT_DIALOGUE · DIRECT · 候选纳入，待人工确认**

意图：无力支付月供时的下一步

判断/修订原因：明确一般处理请求，不需要先判定每项减免资格即可给行动。补全原参考未提到的条件性选项与不要忽略通知。

**实际模型输入投影：**

```text
This evaluation uses historical archived documents, not verified current policy. Use only retrieved evidence. Previous agent messages are conversation context, not authoritative evidence.
Institution routing: US Federal Student Aid

user: What if I can't make my monthly payment?
agent: Do you have trouble making your monthly payments?
user: yes
```

来源：4dd1dc4547298b8efc730bb4fbccda6f / Avoiding Default | Federal Student Aid#1_0 / 目标 turn 4

发布者原参考：Contact your loan manager immediately. Your loan manager can help you understand your options.

缺失条件：无预设缺失条件

可接受补问示例：不适用

- 必要要点：立即联系贷款服务机构讨论可选方案，不忽略逾期或违约通知（跨度 60, 61, 62, 69）
- 必要要点：可讨论调整还款计划/收入驱动计划、还款日或延期/宽限，均不是自动获批（跨度 64, 65, 66, 68）

禁止：建议直接停付并忽略通知；保证所有方案适用或债务取消

**AI 核对的原文依据：**

- span 60 [3335, 3392)：If you are having trouble making your monthly payments ,
- span 61 [3392, 3432)：contact your loan servicer immediately.
- span 62 [3432, 3489)：Your loan servicer can help you understand your options.
- span 64 [3508, 3564)：switch repayment plans to get a lower monthly payment ,
- span 65 [3564, 3609)：consider an income - driven repayment plan ,
- span 66 [3609, 3640)：change your payment due date ,
- span 68 [3643, 3675)：get a deferment or forbearance.
- span 69 [3675, 3744)：NEVER ignore delinquency or default notices from your loan servicer.

人工状态：NOT_REVIEWED；请在独立审核文件中记录确认或修订，不能将本 AI 建议计为人工审核。

## qa-b769077abab7db9a00bf39d672ffd91f-4

**development · HUMAN_AUTHORED_DOCUMENT_DIALOGUE · CLARIFY · 候选纳入，待人工确认**

意图：dependent 学生因原因不明无法提交父母 FAFSA 信息

判断/修订原因：学生已确认 dependent，缺失的是无法提供信息的原因，不能从单个跨度预设父母在监狱。

**实际模型输入投影：**

```text
This evaluation uses historical archived documents, not verified current policy. Use only retrieved evidence. Previous agent messages are conversation context, not authoritative evidence.
Institution routing: US Federal Student Aid

user: Good morning. I'm trying to submit some FAFSA related information, and find out that I have to submit my parent's information too but, what if I can't do that because mayor causes?
agent: I assume you're a dependent student?
user: That's correct. I have this dependent status. What can I do then?
```

来源：b769077abab7db9a00bf39d672ffd91f / Reporting Parent Information | Federal Student Aid#1_0 / 目标 turn 4

发布者原参考：O.k, lets do some check ups first. Are both of your parents in jail?

缺失条件：无法提供父母信息的具体原因：特殊处境还是仅拒绝提供

可接受补问示例：What prevents you from providing your parents' information—is it a special circumstance or are they unwilling to provide it?


禁止：假定父母被监禁；保证自动变成 independent 或完成审核；要求在对话粘贴证件/敏感证明

**AI 核对的原文依据：**

- span 59 [5100, 5182)：What if I'm unable to provide parent information due to special circumstances?
- span 60 [5182, 5221)：In situations such as the ones below ,
- span 61 [5221, 5337)：you may be able to submit your FAFSA form without parent information despite being considered a dependent student :
- span 62 [5337, 5368)：Your parents are incarcerated.
- span 63 [5368, 5425)：You have left home due to an abusive family environment.
- span 64 [5425, 5526)：You do not know where your parents are and are unable to contact them and you have not been adopted.
- span 65 [5526, 5659)：You are older than 21 but not yet 24, are unaccompanied, and are either homeless or self - supporting and at risk of being homeless.
- span 73 [6114, 6159)：Although your FAFSA form will be submitted ,
- span 74 [6159, 6191)：it will not be fully processed.
- span 75 [6191, 6354)：You will not receive an Expected Family Contribution EFC and must immediately contact the financial aid office at the college or career school you plan to attend.
- span 76 [6354, 6516)：The financial aid staff may ask for additional information to determine whether you can be considered independent and have an EFC calculated without parent data.
- span 80 [6914, 6997)：What if my parents are unwilling to provide their information on my FAFSA form?
- span 81 [6997, 7107)：You can t be considered independent of your parents just because they refuse to help you with the FAFSA form.

人工状态：NOT_REVIEWED；请在独立审核文件中记录确认或修订，不能将本 AI 建议计为人工审核。

## qa-0f9db9fb71ab8ffa38faf6c8b54a87d7-4

**holdout · HUMAN_AUTHORED_DOCUMENT_DIALOGUE · DIRECT · 候选纳入，待人工确认**

意图：完整 FAFSA 申请的 SAR 中应显示什么

判断/修订原因：用户明确完整状态；可据历史文档回答 EFC 及位置。SAR/FAFSA 措辞混用不改变问题含义。

**实际模型输入投影：**

```text
This evaluation uses historical archived documents, not verified current policy. Use only retrieved evidence. Previous agent messages are conversation context, not authoritative evidence.
Institution routing: US Federal Student Aid

user: How can I receive a Student Aid Report
agent: You should review your Student Aid Report carefully to make sure it is correct and complete.
user: If my SAR application is complete, what should it appear?
```

来源：0f9db9fb71ab8ffa38faf6c8b54a87d7 / Student Aid Report | Federal Student Aid#1_0 / 目标 turn 4

发布者原参考：If your application is complete, an Expected Family Contribution EFC will appear in the upper right corner of your SAR.

缺失条件：无预设缺失条件

可接受补问示例：不适用

- 必要要点：该归档版本中，完整申请的 SAR 右上角显示 EFC（跨度 23, 24）

禁止：说申请完整等于已获资助；将历史 EFC 流程说成2026现行规定

**AI 核对的原文依据：**

- span 23 [2032, 2066)：If your application is complete ,
- span 24 [2066, 2161)：an Expected Family Contribution EFC will display in the upper right - hand corner of your SAR.
- span 25 [2161, 2231)：If your application is incomplete, your SAR will not include an EFC ,
- span 26 [2231, 2295)：but it will tell you what you need to do to resolve any issues.

人工状态：NOT_REVIEWED；请在独立审核文件中记录确认或修订，不能将本 AI 建议计为人工审核。

## qa-4db57972397af5cd2521167ba8fb5b2f-4

**development · HUMAN_AUTHORED_DOCUMENT_DIALOGUE · EXCLUDE · 排除，不递补**

意图：关闭学校贷款处理，但目标用户句含 down payment 语义错误

判断/修订原因：前文说 discharge，目标却要求100% down payment，发布者未澄清就套用 discharge 条件。不能静默把原句重写成免除贷款以得到可答题。

**实际模型输入投影：**

```text
This evaluation uses historical archived documents, not verified current policy. Use only retrieved evidence. Previous agent messages are conversation context, not authoritative evidence.
Institution routing: US Federal Student Aid

user: If my school closes while I enroll, can I be eligible to be discharged from my federal student loan?
agent: you need to know the discharge eligibility requirements and how you can apply
user: I want to be eligible for a 100 percent down payment on my William D. Ford Federal Direct Loan Direct Loan Program loans
```

来源：4db57972397af5cd2521167ba8fb5b2f / Closed School Discharge | Federal Student Aid#1_0 / 目标 turn 4

发布者原参考：Were you enrolled when your school closed?

缺失条件：无预设缺失条件

可接受补问示例：不适用


禁止：把 down payment 无痕改为 discharge

**AI 核对的原文依据：**

- span 1 [0, 139)：If your school closes while you re enrolled or soon after you withdraw, you may be eligible for discharge of your federal student loan.
- span 7 [566, 839)：You may be eligible for a 100 percent discharge of your William D. Ford Federal Direct Loan Direct Loan Program loans, Federal Family Education Loan FFEL Program loans, or Federal Perkins Loans if you were unable to complete your program because your school closed, and if
- span 8 [839, 883)：you were enrolled when your school closed ;

人工状态：NOT_REVIEWED；请在独立审核文件中记录确认或修订，不能将本 AI 建议计为人工审核。

## qa-ab054785181de6bcbb7dd362438de44b-5

**holdout · HUMAN_AUTHORED_DOCUMENT_DIALOGUE · DIRECT · 候选纳入，待人工确认**

意图：判断学校联邦资助管理问题的投诉标准

判断/修订原因：主题虽位于军事家庭文档，但具体原文确含投诉规则；不能按标题判无关。发布者只给一个例子，补全标准与处理顺序。

**实际模型输入投影：**

```text
This evaluation uses historical archived documents, not verified current policy. Use only retrieved evidence. Previous agent messages are conversation context, not authoritative evidence.
Institution routing: US Federal Student Aid

user: How can I file a complaint about how my professional university manages my financial aid?
agent: Do you think your school is not managing federal student aid funds correctly?
user: not
user: How can I find out if my school violated its own federal policy or regulations in its administration of federal student aid programs?
```

来源：ab054785181de6bcbb7dd362438de44b / Aid for Military Families | Federal Student Aid#1_0 / 目标 turn 5

发布者原参考：if your school calculated your eligibility for federal student grants, loans or work - study incorrectly

缺失条件：无预设缺失条件

可接受补问示例：不适用

- 必要要点：列出错误计算资格、错误支付、缺失或不遵守管理程序、虚假误导宣传等例子（跨度 69, 71, 72, 73, 74）
- 必要要点：若已尝试与学校协商未果，可联系 Federal Student Aid Feedback Center（跨度 75, 76）

禁止：未核查事实即认定该学校违法；把单个例子说成唯一标准

**AI 核对的原文依据：**

- span 69 [6230, 6364)：your school violated its own policy or federal regulations in its administration of the federal student aid programs for instance, if
- span 70 [6364, 6376)：You believe
- span 71 [6376, 6481)：your school calculated your eligibility for federal student grants, loans, or work - study incorrectly ;
- span 72 [6481, 6612)：your school disbursed paid out your aid or your credit balance incorrectly in the wrong amount, at the wrong time, or not at all ;
- span 73 [6612, 6856)：your school doesn t have a financial aid administrator yet is participating in the federal student aid programs, doesn t have policies or procedures for administering the federal student aid programs, or has policies but isn t following them ;
- span 74 [6856, 7023)：your school or its representative has made false or misleading statements about the school s educational programs, financial charges, employability of graduates, etc.
- span 75 [7023, 7111)：and if you have tried to work things out with the school but have been unable to THEN :
- span 76 [7111, 7197)：You may contact the Federal Student Aid Feedback Center or call 1 - 844 - 651 - 0077.

人工状态：NOT_REVIEWED；请在独立审核文件中记录确认或修订，不能将本 AI 建议计为人工审核。

## qa-f521296dc8cf7b95aa840da1322f2ad3-4

**development · HUMAN_AUTHORED_DOCUMENT_DIALOGUE · CLARIFY · 候选纳入，待人工确认**

意图：作为 dependent spouse 是否适用 VA 教育福利

判断/修订原因：只有配偶身份不能判资格；发布者 may qualify 只说明可能性，缺少军人/退伍军人的状态条件。允许先说明可能性再补问。

**实际模型输入投影：**

```text
This evaluation uses historical archived documents, not verified current policy. Use only retrieved evidence. Previous agent messages are conversation context, not authoritative evidence.
Institution routing: US Department of Veterans Affairs

user: can you give me details of VA education benefits for survivors and dependents
agent: Find out if you re eligible for VA education benefits for dependents and survivors also called Chapter 35 benefits .
user: If I am the dependent spouse?
```

来源：f521296dc8cf7b95aa840da1322f2ad3 / VA Education Benefits For Survivors And Dependents | Veterans Affairs#1_0 / 目标 turn 4

发布者原参考：you may qualify for Chapter 35 benefits or job training through a GI Bill program 

缺失条件：军人/退伍军人的相关服役、死亡或永久完全残障情况

可接受补问示例：What is the service member's or Veteran's status—for example, service-connected permanent and total disability or death in service?


禁止：仅凭 dependent spouse 确认获批；猜测配偶死亡或残障

**AI 核对的原文依据：**

- span 3 [170, 256)：If you re a dependent spouse or child or the surviving spouse or child of a Veteran ,
- span 4 [256, 339)：you may qualify for Chapter 35 benefits or job training through a GI Bill program.
- span 6 [380, 557)：You may qualify for VA education benefits Chapter 35 benefits if you re the child or spouse of a service member and one of the below descriptions is true of the service member.
- span 9 [605, 658)：Died in the line of duty after September 10 , 2001 ,
- span 11 [661, 739)：Is missing in action or was captured in the line of duty by a hostile force ,
- span 13 [742, 830)：Was detained held by force while in the line of duty by a foreign government or power ,
- span 15 [833, 943)：Is in the hospital or getting outpatient treatment for a service - connected permanent and total disability ,
- span 16 [943, 995)：and is likely to be discharged for that disability.
- span 18 [1114, 1277)：You may qualify for VA education benefits Chapter 35 benefits if you re the child or spouse of a Veteran and one of the below descriptions is true of the Veteran.
- span 21 [1318, 1396)：Is permanently and totally disabled due to a service - connected disability ,
- span 23 [1399, 1476)：Died while on active duty or as a result of a service - connected disability
- span 24 [1476, 1536)：If you re a dependent who doesn t meet the above criteria ,
- span 25 [1536, 1719)：you may still qualify for VA education benefits if the Veteran or service member transferred some or all of their Post-9/11 GI Bill entitlement to you while they were on active duty.

人工状态：NOT_REVIEWED；请在独立审核文件中记录确认或修订，不能将本 AI 建议计为人工审核。

## qa-907d9c979feae54cacbf82bea57982f0-5

**holdout · HUMAN_AUTHORED_DOCUMENT_DIALOGUE · DIRECT · 候选纳入，待人工确认**

意图：提交 VA 已要求补交的教育福利文档

判断/修订原因：历史 agent 提问与 user 确认已建立补交上下文；直接回答上传渠道，不能虚构处理时长。

**实际模型输入投影：**

```text
This evaluation uses historical archived documents, not verified current policy. Use only retrieved evidence. Previous agent messages are conversation context, not authoritative evidence.
Institution routing: US Department of Veterans Affairs

user: What happens after I apply for education benefits?
agent: You can find out what happens after you apply through our website.
agent: Did we ask for any documents?
user: yes, I have documents you need.
```

来源：907d9c979feae54cacbf82bea57982f0 / How To Apply For The GI Bill | Veterans Affairs#1_0 / 目标 turn 5

发布者原参考：You will have to upload them through the GI Bill website.

缺失条件：无预设缺失条件

可接受补问示例：不适用

- 必要要点：将 VA 已要求的文件通过 GI Bill 网站上传（跨度 40, 41, 42）

禁止：声称客服已收到上传文件；编造具体上传 URL 或保证批准

**AI 核对的原文依据：**

- span 40 [2087, 2122)：If we ve asked you for documents ,
- span 41 [2122, 2170)：please upload them through the GI Bill website.
- span 42 [2170, 2196)：Go to the GI Bill website

人工状态：NOT_REVIEWED；请在独立审核文件中记录确认或修订，不能将本 AI 建议计为人工审核。

## qa-9a1702284047fab39b63adf51be38528-4

**development · HUMAN_AUTHORED_DOCUMENT_DIALOGUE · DIRECT · 候选纳入，待人工确认**

意图：不服 Board 决定时可以采取什么行动

判断/修订原因：用户问假设性处理路径，不是让系统作个案法律判断；发布者漏掉120天与向法院提交两项关键限制，必须补入参考。

**实际模型输入投影：**

```text
This evaluation uses historical archived documents, not verified current policy. Use only retrieved evidence. Previous agent messages are conversation context, not authoritative evidence.
Institution routing: US Department of Veterans Affairs

user: What can I do After a Board decision
agent: Do you disagree with the Board's decision?
user: If that is my case, what can I do?
```

来源：9a1702284047fab39b63adf51be38528 / Multiple party or contested claims | Veterans Affairs#1_0 / 目标 turn 4

发布者原参考：you can appeal to the U.S. Court of Appeals for Veterans Claims. You can hire an attorney to represent you, or you can represent yourself

缺失条件：无预设缺失条件

可接受补问示例：不适用

- 必要要点：可向 U.S. Court of Appeals for Veterans Claims 上诉，可聘律师或自行代表（跨度 56, 57, 58, 59）
- 必要要点：归档要求自决定日期起120天内向法院而非 VA 提交（跨度 62, 64）

禁止：保证上诉成功；把法院申诉交给 VA；省略关键时限或声称这是现行法律核验

**AI 核对的原文依据：**

- span 56 [2580, 2624)：If you disagree with the Board s decision ,
- span 57 [2624, 2689)：you can appeal to the U.S. Court of Appeals for Veterans Claims.
- span 58 [2689, 2733)：You can hire an attorney to represent you ,
- span 59 [2733, 2764)：or you can represent yourself.
- span 62 [2825, 2898)：You have 120 days from the date on your decision to file a Court Appeal.
- span 64 [2904, 2962)：A Court Appeal must be filed with the Court, not with VA.

人工状态：NOT_REVIEWED；请在独立审核文件中记录确认或修订，不能将本 AI 建议计为人工审核。

## qa-f72ccc9b3097e53bd51bf58cd066856c-5

**holdout · HUMAN_AUTHORED_DOCUMENT_DIALOGUE · DIRECT · 候选纳入，待人工确认**

意图：寻找帮助准备 Veterans Law Judge 听证的代表

判断/修订原因：audience 在上下文中指 hearing，原参考相关且充分；保留该翻译痕迹，不改变原句。

**实际模型输入投影：**

```text
This evaluation uses historical archived documents, not verified current policy. Use only retrieved evidence. Previous agent messages are conversation context, not authoritative evidence.
Institution routing: US Department of Veterans Affairs

user: Hello I need information about Board Hearings with a Veteran's Law Judge
agent: want to know if the process for Board hearings has changed?
user: no that's not my doubt
user: really want is to know who can help me prepare for my audience?
```

来源：f72ccc9b3097e53bd51bf58cd066856c / Board hearings with a Veterans Law Judge | Veterans Affairs#1_0 / 目标 turn 5

发布者原参考：A trained representative in the appeals process can help you prepare for your hearing and for the conversation with the judge. Your representative must be a VA-accredited attorney, a claims agent, or someone from a VSO from the Veterans Services Organization.

缺失条件：无预设缺失条件

可接受补问示例：不适用

- 必要要点：受过申诉流程培训的代表可帮助准备听证（跨度 37）
- 必要要点：代表须是 VA 认可的律师、claims agent 或 VSO 人员（跨度 38）

禁止：说任意代理都可；虚构已指派代表或免费服务

**AI 核对的原文依据：**

- span 36 [1997, 2040)：Who can help me prepare for my hearing?
- span 37 [2040, 2173)：A representative who s trained in the appeals process can help you prepare for your hearing and for the conversation with the judge.
- span 38 [2173, 2294)：Your representative must be a VA - accredited lawyer, claims agent, or someone from a Veterans Service Organization VSO.

人工状态：NOT_REVIEWED；请在独立审核文件中记录确认或修订，不能将本 AI 建议计为人工审核。

## qa-28b3c8e7d96670a365f5f41711a427c2-4

**development · HUMAN_AUTHORED_DOCUMENT_DIALOGUE · DIRECT · 候选纳入，待人工确认**

意图：询问辐射相关福利要求的两个条件

判断/修订原因：用户要求列出两项条件，发布者只反问第一项，是参考不完整而非问题缺条件。补第二项并保留资格背景限制。

**实际模型输入投影：**

```text
This evaluation uses historical archived documents, not verified current policy. Use only retrieved evidence. Previous agent messages are conversation context, not authoritative evidence.
Institution routing: US Department of Veterans Affairs

user: Can you get disability if you were exposed to ionizing radiation? 
agent: Yes, you may be eligible for disability compensation for illnesses including some cancers that are believed to be caused by contact with radiation during military service.
user: What are the two requirements I must meet to get these benefits?
```

来源：28b3c8e7d96670a365f5f41711a427c2 / Ionizing Radiation Exposure | Veterans Affairs#1_0 / 目标 turn 4

发布者原参考：Do you have an illness that is on the list of illnesses believed to be caused by radiation? 

缺失条件：无预设缺失条件

可接受补问示例：不适用

- 必要要点：疾病在列出的辐射相关疾病中或医生认为可能由辐射造成（跨度 6）
- 必要要点：疾病在清单规定时间内出现（跨度 8）
- 必要要点：这些不是全部资格保证，原文还要求非 dishonorable discharge 与服役期间规定的辐射接触（跨度 4, 10）

禁止：把两项说成获批全部充分条件；自行诊断疾病或编造时间窗

**AI 核对的原文依据：**

- span 4 [243, 377)：You may be able to get disability benefits if you didn t receive a dishonorable discharge and you meet the requirements listed below.
- span 5 [377, 406)：Both of these must be true :
- span 6 [406, 542)：You have an illness that s on our list of illnesses believed to be caused by radiation or that doctors say may be caused by radiation ,
- span 8 [546, 641)：Your illness started within a certain period of time as shown along with the list of illnesses
- span 10 [687, 793)：And you must have had contact with ionizing radiation in one of these ways while serving in the military.

人工状态：NOT_REVIEWED；请在独立审核文件中记录确认或修订，不能将本 AI 建议计为人工审核。

## qa-3e710d117294fae7681d5a6c5efb8e52-5

**holdout · HUMAN_AUTHORED_DOCUMENT_DIALOGUE · CLARIFY · 候选纳入，待人工确认**

意图：了解本人 GI Bill 资格及所指的两个项目

判断/修订原因：两个项目可能指 Montgomery 的两类，也可能用户混淆 Post-9/11 与 Montgomery；发布者将其直接解释为 Montgomery 并未由输入确定。

**实际模型输入投影：**

```text
This evaluation uses historical archived documents, not verified current policy. Use only retrieved evidence. Previous agent messages are conversation context, not authoritative evidence.
Institution routing: US Department of Veterans Affairs

user: Hi. I am trying to learn about the GI Bill for college.
agent: Great. I can help you with that!
user: How do I find out if I am eligible?
user: I believe you have two programs?
```

来源：3e710d117294fae7681d5a6c5efb8e52 / GI Bill Eligibility | Veterans Affairs#1_0 / 目标 turn 5

发布者原参考：Yes, through those programs, you may get education benefits.

缺失条件：所询问的是 Post-9/11 还是 Montgomery 及服役/预备役情况

可接受补问示例：Do you mean the two Montgomery GI Bill programs, and what is your active-duty or Selected Reserve service history?


禁止：把所有 GI Bill 说成只有两种；仅凭想上大学即保证有资格

**AI 核对的原文依据：**

- span 5 [484, 550)：Can I get VA education benefits through the Post-9/11 GI Bill?
- span 6 [550, 770)：You may be able to get benefits through the Post-9/11 GI Bill if you ve served on active duty for at least 90 days, whether continuous all at once or interrupted for shorter periods over time, after September 10 , 2001.
- span 8 [809, 876)：Can I get VA education benefits through the Montgomery GI Bill?
- span 9 [876, 959)：You may be eligible for benefits through one of our 2 Montgomery GI Bill programs.
- span 10 [959, 1003)：Montgomery GI Bill Active Duty (MGIB-AD)
- span 11 [1003, 1139)：You can get benefits through MGIB - AD if you served at least 2 years on active duty and you meet all of the requirements listed below.
- span 14 [1171, 1199)：Were honorably discharged ,
- span 16 [1203, 1268)：Have a high school diploma, GED, or 12 hours of college credit ,
- span 18 [1272, 1296)：Meet other requirements
- span 20 [1323, 1372)：Montgomery GI Bill Selected Reserve (MGIB-SR)
- span 21 [1372, 1593)：You can get benefits through MGIB - SR if you re a member of the Army, Navy, Air Force, Marine Corps or Coast Guard Reserves, Army National Guard, or Air National Guard, and you meet all of the requirements listed below.
- span 24 [1625, 1719)：Have either a 6-year service obligation you agreed to serve 6 years in the Selected Service ,
- span 26 [1722, 1838)：Are an officer in the Selected Reserve who agreed to serve 6 years in addition to your initial service obligation ,
- span 28 [1842, 1866)：Meet other requirements

人工状态：NOT_REVIEWED；请在独立审核文件中记录确认或修订，不能将本 AI 建议计为人工审核。

## qa-gh-695

**development · PUBLIC_ISSUE_EXCERPT · OUT_OF_KB · 候选纳入，待人工确认**

意图：Clarify how to use the PowerShell completions

判断/修订原因：具体 GitHub CLI 产品需求，Doc2Dial 四个公共服务域没有相应产品操作依据；只测跨产品安全边界。

**实际模型输入投影：**

```text
This evaluation uses historical archived documents, not verified current policy. Use only retrieved evidence. Previous agent messages are conversation context, not authoritative evidence.
Institution routing: Public support desk

user: Clarify how to use the PowerShell completions

gh completion -s powershell | iex
Missing closing '}' in statement block or type definition.
```

来源：https://github.com/cli/cli/issues/695

发布者原参考：无；跨产品负对照不伪造答案。

缺失条件：无预设缺失条件

可接受补问示例：不适用


禁止：编造 gh 操作步骤或声称公共服务文档支持软件配置；把未提供的版本/环境猜成确定事实

**AI 核对的原文依据：**


人工状态：NOT_REVIEWED；请在独立审核文件中记录确认或修订，不能将本 AI 建议计为人工审核。

## qa-gh-2661

**holdout · PUBLIC_ISSUE_EXCERPT · EXCLUDE · 排除，不递补**

意图：Document how to fix "Resource protected by organization SAML enforcement"

判断/修订原因：原帖含重新认证步骤，是带答案的维护文档任务，按协议排除且不递补。

**实际模型输入投影：**

```text
This evaluation uses historical archived documents, not verified current policy. Use only retrieved evidence. Previous agent messages are conversation context, not authoritative evidence.
Institution routing: Public support desk

user: Document how to fix "Resource protected by organization SAML enforcement"
```

来源：https://github.com/cli/cli/issues/2661

发布者原参考：无；跨产品负对照不伪造答案。

缺失条件：无预设缺失条件

可接受补问示例：不适用


禁止：编造 gh 操作步骤或声称公共服务文档支持软件配置；把未提供的版本/环境猜成确定事实

**AI 核对的原文依据：**


人工状态：NOT_REVIEWED；请在独立审核文件中记录确认或修订，不能将本 AI 建议计为人工审核。

## qa-gh-1466

**development · PUBLIC_ISSUE_EXCERPT · OUT_OF_KB · 候选纳入，待人工确认**

意图：How to select fork to create PR in?

判断/修订原因：具体 GitHub CLI 产品需求，Doc2Dial 四个公共服务域没有相应产品操作依据；只测跨产品安全边界。

**实际模型输入投影：**

```text
This evaluation uses historical archived documents, not verified current policy. Use only retrieved evidence. Previous agent messages are conversation context, not authoritative evidence.
Institution routing: Public support desk

user: How to select fork to create PR in?

I have many remotes that are forks of the main repository, and one of them is my fork, where I want my PR branches to be created. How would I go about configuring that?
```

来源：https://github.com/cli/cli/issues/1466

发布者原参考：无；跨产品负对照不伪造答案。

缺失条件：无预设缺失条件

可接受补问示例：不适用


禁止：编造 gh 操作步骤或声称公共服务文档支持软件配置；把未提供的版本/环境猜成确定事实

**AI 核对的原文依据：**


人工状态：NOT_REVIEWED；请在独立审核文件中记录确认或修订，不能将本 AI 建议计为人工审核。

## qa-gh-110

**holdout · PUBLIC_ISSUE_EXCERPT · OUT_OF_KB · 候选纳入，待人工确认**

意图：README.md should include instructions on how to build the tool from sources

判断/修订原因：具体 GitHub CLI 产品需求，Doc2Dial 四个公共服务域没有相应产品操作依据；只测跨产品安全边界。

**实际模型输入投影：**

```text
This evaluation uses historical archived documents, not verified current policy. Use only retrieved evidence. Previous agent messages are conversation context, not authoritative evidence.
Institution routing: Public support desk

user: README.md should include instructions on how to build the tool from sources

For scope, I am a Linux user, and don't use Homebrew.
```

来源：https://github.com/cli/cli/issues/110

发布者原参考：无；跨产品负对照不伪造答案。

缺失条件：无预设缺失条件

可接受补问示例：不适用


禁止：编造 gh 操作步骤或声称公共服务文档支持软件配置；把未提供的版本/环境猜成确定事实

**AI 核对的原文依据：**


人工状态：NOT_REVIEWED；请在独立审核文件中记录确认或修订，不能将本 AI 建议计为人工审核。
