export type ContestRule = {
  id: string;
  title: string;
  requirement: string;
  implementationPolicy: string;
  source: string;
};

export const contestRules: ContestRule[] = [
  {
    id: 'content-goal',
    title: '3D object/scene creation and impressive rendering',
    requirement:
      'Reconstruct, generate, or handcraft 3D object(s) or a scene, then render it as an impressive video.',
    implementationPolicy:
      '모든 구현은 절차적/수작업 모델링과 브라우저 기반 WebGL 렌더링을 우선해, 소스 코드만으로 재현 가능해야 한다.',
    source: 'KAIST CS479 3D Rendering Contest > What to Do',
  },
  {
    id: 'no-commercial-software',
    title: 'No commercial software',
    requirement: 'Do not use commercial software; violation results in zero score.',
    implementationPolicy:
      '유료/상용 DCC나 렌더러에 의존하지 않는다. 뷰어와 렌더링은 오픈소스 도구를 사용한다.',
    source: 'KAIST CS479 3D Rendering Contest > Important Notes',
  },
  {
    id: 'no-3d-assets',
    title: 'No external 3D assets',
    requirement: 'Do not use any 3D assets; violation results in zero score.',
    implementationPolicy:
      '외부 3D 모델/메시/스캔 데이터를 가져오지 않는다. 필요한 형상은 코드로 생성하거나 직접 제작한다.',
    source: 'KAIST CS479 3D Rendering Contest > Important Notes',
  },
  {
    id: 'no-paid-or-closed-models',
    title: 'No paid neural models or closed-source 3D tools',
    requirement:
      'Do not use paid neural network models or closed-source software such as PolyCam/Luma AI.',
    implementationPolicy:
      '신경망/생성형 도구를 쓰는 경우 무료·오픈 접근 가능한 것만 검토하고, 사용 여부와 출처를 명시한다.',
    source: 'KAIST CS479 3D Rendering Contest > Important Notes',
  },
  {
    id: 'no-blender-rendering',
    title: 'No Blender rendering',
    requirement: 'Blender may be used for modeling/texturing but not for rendering.',
    implementationPolicy:
      'Blender는 필요 시 모델링/텍스처링 보조까지만 허용하고, 최종 렌더링은 브라우저/WebGL 등 허용 렌더러에서 수행한다.',
    source: 'KAIST CS479 3D Rendering Contest > Important Notes',
  },
  {
    id: 'submit-formats',
    title: 'Submission format limits',
    requirement:
      'PNG representative image <=1920x1080 and <=5MB; MP4 video <=10 seconds, <=1920x1080 and <=50MB; one 3D content piece <=100MB; reproducible source/data; write-up <=4 A4 pages excluding references.',
    implementationPolicy:
      '대표 PNG, 10초 이하 영상, 100MB 이하 3D 콘텐츠, 재현 가능한 소스/데이터, 4쪽 이하 보고서 조건을 구현/검증 체크리스트에 포함한다.',
    source: 'KAIST CS479 3D Rendering Contest > What to Submit',
  },
  {
    id: 'citation',
    title: 'Cite code/resources',
    requirement:
      'All existing code, models, and assets must be cited; missing references can be treated as misconduct/zero score.',
    implementationPolicy:
      '외부 코드, 라이브러리, 참고 자료, 비-3D 에셋이 생기면 README/보고서와 앱 내 규정 영역에 출처를 기록한다.',
    source: 'KAIST CS479 3D Rendering Contest > What to Submit',
  },
];
